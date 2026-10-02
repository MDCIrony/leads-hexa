"""Delivery process: relays the outbox to Kafka, webhooks and RabbitMQ.

Its own compose service, not threads inside the API, so a slow broker or a
webhook that times out can never take request capacity with it, and the API can
restart without interrupting delivery. Run with `python -m infrastructure.worker`."""
