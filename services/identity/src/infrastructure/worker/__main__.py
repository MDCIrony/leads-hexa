"""Outbox relay process of the identity service.

Runs apart from the API so that an unreachable broker cannot hold request handling
back, and the two restart independently."""
import sys

from infrastructure.worker.main import main

sys.exit(main())
