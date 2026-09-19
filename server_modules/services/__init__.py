"""Shared studio services: MongoDB, cancellation, images, and the pickers."""
import threading

# Mutex lock preventing concurrent npm install operations in the same directory.
NPM_LOCK = threading.Lock()
