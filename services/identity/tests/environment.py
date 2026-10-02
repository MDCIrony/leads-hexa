"""Test-only values conftest puts in the environment, importable by the tests that
need the plaintext behind them (the service client's secret)."""
import hashlib

SIGNING_KEYS = "test-1=We6wZYLn41lq5z4FdSgMD7Jmla3wUOhIe8MBaNQiuuk"
MFA_ENCRYPTION_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="

SERVICE_CLIENT_ID = "lead-core"
SERVICE_CLIENT_SECRET = "lead-core-test-secret"
SERVICE_CLIENTS = (
    f"{SERVICE_CLIENT_ID}:identity:{hashlib.sha256(SERVICE_CLIENT_SECRET.encode()).hexdigest()}"
)
