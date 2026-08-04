# Cron state

This directory is where Hermes scheduler state (job definitions + execution
history) is snapshotted by `build-identity.sh`. On a fresh install it starts
empty — cron jobs are created at runtime by the agent.

Nothing sensitive lives here by policy (executions only, no tokens).
