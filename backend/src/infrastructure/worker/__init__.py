"""Delivery process: relays the outbox to Kafka, webhooks and RabbitMQ.

Its own compose service, not threads inside the API, so a slow broker or a
webhook that times out can never take request capacity with it, and the API can
restart without interrupting delivery. The notification consumers moved to
notifications-worker in F2. Run with `python -m infrastructure.worker`."""
