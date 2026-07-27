#!/usr/bin/env python
"""Publish canonical universal player trade values after stats and projections refresh."""
from __future__ import annotations
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.services.player_trade_value import VALUE_POLICY_VERSION, calculate_weekly_trade_values

parser = argparse.ArgumentParser()
parser.add_argument("--season", type=int, required=True)
parser.add_argument("--week", type=int, required=True)
parser.add_argument("--policy-version", default=VALUE_POLICY_VERSION)
parser.add_argument("--database-url", default=settings.database_url)

if __name__ == "__main__":
    args = parser.parse_args(); ensure_models_registered()
    with Session(create_engine(args.database_url, pool_pre_ping=True)) as db:
        print(calculate_weekly_trade_values(db, season=args.season, week=args.week, policy_version=args.policy_version)); db.commit()
