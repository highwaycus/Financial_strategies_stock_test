# Stock Strategy Experiments

This repository turns two stock-trading ideas into Python experiments that can be tested with market data. One looks for a moving-average alignment signal, while the other tests the delayed result of following a reference portfolio.

## What I wanted to test

A trading idea usually sounds simple until every condition has to be written down. I use this repository to turn those ideas into rules that can be backtested before I consider using them in real trading.

## Experiments

### 1. Right-Angle Attack Method

**File:** `TW_stock_attack_method.py`

The signal appears when all rolling-average price lines are rising and ordered from short to long windows—for example, the 3-day average is above the 5-day average.

### 2. Delayed portfolio-following strategy

**File:** `tracking_master_strategy.py`

This experiment follows the changes in a reference portfolio. Because those changes are only visible after a delay, the first question is whether the delayed version still produces a useful return in backtesting.

## Status

These are strategy experiments, not a production trading system. The repository is mainly a record of how I translate an investment idea into code and testable conditions.
