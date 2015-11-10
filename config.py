listen_port = 8212

# fading out for the client (30 fps), so 1/30 fades in out within a second,
# 1/300 fades it out in 10 seconds
client_decay = 1.0 / (30 * 10)
# fading out for the server
server_decay = 1.0 / (30 * 10)

# how much the points wiggle about in pixels
server_jitter = 0.3

config = {
    'width': 1200,
    'height': 1600
}
