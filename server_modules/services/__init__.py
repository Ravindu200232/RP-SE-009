"""Shared studio services: MongoDB, cancellation, images, and the pickers."""
import threading

# npm rewrites node_modules and package-lock.json in place, so two installs in
# the same tree at once corrupt both. One lock, shared by everything that can
# start one: the builder installing dependencies and the QA harness installing
# a runner are the two that collide.
NPM_LOCK = threading.Lock()
