"""Small, fixed v2 architectures; all forecasts are 56 observed days to 14 days.

Calendar channels describe historical days, independently of transaction values.
The Transformer mask embedding is used only for self-supervised reconstruction.
"""
from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

KINDS = ("mlp", "tcn", "gru", "transformer")
CONTEXT, HORIZON, AUXILIARY = 56, 14, 43


class CausalBlock(nn.Module):
    def __init__(self, inputs: int, width: int, dilation: int):
        super().__init__()
        self.padding = 2 * dilation
        self.conv1 = nn.Conv1d(inputs, width, 3, dilation=dilation)
        self.conv2 = nn.Conv1d(width, width, 3, dilation=dilation)
        self.skip = nn.Conv1d(inputs, width, 1) if inputs != width else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        hidden = F.relu(self.conv1(F.pad(x, (self.padding, 0))))
        hidden = self.conv2(F.pad(hidden, (self.padding, 0)))
        return F.relu(hidden + self.skip(x))


class TransformerTrunk(nn.Module):
    def __init__(self):
        super().__init__()
        self.projection = nn.Linear(3, 32)
        self.mask_embedding = nn.Parameter(torch.zeros(32))
        nn.init.normal_(self.mask_embedding, std=0.02)
        positions = torch.arange(CONTEXT, dtype=torch.float32)[:, None]
        rates = torch.exp(torch.arange(0, 32, 2, dtype=torch.float32) * (-math.log(10000.) / 32))
        encoding = torch.zeros(CONTEXT, 32)
        encoding[:, 0::2], encoding[:, 1::2] = torch.sin(positions * rates), torch.cos(positions * rates)
        self.register_buffer("position_encoding", encoding)
        # Separate construction avoids identical cloned initialization in layers.
        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(32, 2, dim_feedforward=64, dropout=0.,
                                       activation="relu", batch_first=True)
            for _ in range(2)
        ])

    def forward(self, sequence: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        hidden = self.projection(sequence) + self.position_encoding[None, :, :]
        if mask is not None:
            hidden = hidden + mask[:, :, None].to(hidden.dtype) * self.mask_embedding
        for layer in self.layers:
            hidden = layer(hidden)
        return hidden


class SequenceModel(nn.Module):
    """Standardized feature vector for MLP; scaled sequence + standard aux otherwise."""
    def __init__(self, kind: str):
        super().__init__()
        if kind not in KINDS:
            raise ValueError(f"unknown architecture: {kind}")
        self.kind = kind
        if kind == "mlp":
            self.head = nn.Sequential(nn.Linear(99, 64), nn.ReLU(), nn.Linear(64, 32),
                                      nn.ReLU(), nn.Linear(32, HORIZON), nn.Softplus())
        elif kind == "tcn":
            self.trunk = nn.Sequential(*[
                CausalBlock(3 if i == 0 else 24, 24, dilation)
                for i, dilation in enumerate((1, 2, 4, 8))
            ])
            self.head = nn.Sequential(nn.Linear(24 + AUXILIARY, 32), nn.ReLU(),
                                      nn.Linear(32, HORIZON), nn.Softplus())
        elif kind == "gru":
            self.trunk = nn.GRU(3, 48, num_layers=1, batch_first=True)
            self.head = nn.Sequential(nn.Linear(48 + AUXILIARY, 32), nn.ReLU(),
                                      nn.Linear(32, HORIZON), nn.Softplus())
        else:
            self.trunk = TransformerTrunk()
            self.head = nn.Sequential(nn.Linear(32 + AUXILIARY, 16), nn.ReLU(),
                                      nn.Linear(16, HORIZON), nn.Softplus())

    def forward(self, sequence: torch.Tensor, auxiliary: torch.Tensor,
                flat_features: torch.Tensor) -> torch.Tensor:
        if self.kind == "mlp":
            return self.head(flat_features)
        if self.kind == "tcn":
            state = self.trunk(sequence.transpose(1, 2))[:, :, -1]
        elif self.kind == "gru":
            _, final = self.trunk(sequence)
            state = final[-1]
        else:
            state = self.trunk(sequence).mean(dim=1)
        return self.head(torch.cat((state, auxiliary), dim=1))


def make_model(kind: str, seed: int = 0) -> SequenceModel:
    """Initialize reproducibly without advancing the caller's Torch RNG."""
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = SequenceModel(kind)
    if parameter_count(model) >= 50_000:
        raise ValueError("architecture violates frozen 50,000-parameter ceiling")
    return model


def parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
