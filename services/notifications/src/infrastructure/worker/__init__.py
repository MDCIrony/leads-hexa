"""Consumer process of the notifications service.

Runs apart from the API so that a slow or failing consumer cannot take request
handling down with it, and so the two scale and restart independently."""
