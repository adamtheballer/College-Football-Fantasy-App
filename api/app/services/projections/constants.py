from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DefenseMultipliers:
    yards: float
    catch: float
    td: float
    turnover: float


PASS_DEF_MULTIPLIERS = {
    "Elite": DefenseMultipliers(yards=0.90, catch=0.94, td=0.85, turnover=1.15),
    "Strong": DefenseMultipliers(yards=0.95, catch=0.97, td=0.92, turnover=1.08),
    "Average": DefenseMultipliers(yards=1.00, catch=1.00, td=1.00, turnover=1.00),
    "Weak": DefenseMultipliers(yards=1.05, catch=1.03, td=1.08, turnover=0.95),
    "Poor": DefenseMultipliers(yards=1.10, catch=1.06, td=1.15, turnover=0.90),
}

RUSH_DEF_MULTIPLIERS = {
    "Elite": DefenseMultipliers(yards=0.90, catch=0.96, td=0.85, turnover=1.10),
    "Strong": DefenseMultipliers(yards=0.95, catch=0.98, td=0.92, turnover=1.05),
    "Average": DefenseMultipliers(yards=1.00, catch=1.00, td=1.00, turnover=1.00),
    "Weak": DefenseMultipliers(yards=1.05, catch=1.02, td=1.08, turnover=0.95),
    "Poor": DefenseMultipliers(yards=1.10, catch=1.04, td=1.15, turnover=0.90),
}


def tier_from_percentile(percentile: float) -> str:
    if percentile >= 0.90:
        return "Elite"
    if percentile >= 0.70:
        return "Strong"
    if percentile >= 0.30:
        return "Average"
    if percentile >= 0.10:
        return "Weak"
    return "Poor"


DEFAULT_RB_CARRY_SHARES = [0.62, 0.25, 0.13]
DEFAULT_WR_TARGET_SHARES = [0.26, 0.20, 0.15, 0.10]
DEFAULT_TE_TARGET_SHARE = 0.12
DEFAULT_RB_TARGET_SHARE = 0.17
