"""Transport-agnostic player protocol definitions.

Shared by the MQTT player request/response handlers (`app.mqtt.player_requests`)
and the HTTPS player RPC backend (`app.routers.player_rpc`). Nothing in this
package may depend on a specific transport, so a request handled over either
transport produces identical results.
"""
