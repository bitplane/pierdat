#!/bin/sh

# Start pierdatd in the background
/usr/bin/pierdatd &

# Start the main application (replace this with your own)
exec "$@"