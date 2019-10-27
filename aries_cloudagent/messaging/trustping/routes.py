"""Trust ping admin routes."""

from aiohttp import web
from aiohttp_apispec import docs

from ..connections.models.connection_record import ConnectionRecord
from .messages.ping import Ping
from ...storage.error import StorageNotFoundError


@docs(tags=["trustping"], summary="Send a trust ping to a connection")
async def connections_send_ping(request: web.BaseRequest):
    """
    Request handler for sending a trust ping to a connection.

    Args:
        request: aiohttp request object

    """
    context = request.app["request_context"]
    connection_id = request.match_info["id"]
    outbound_handler = request.app["outbound_message_router"]

    try:
        connection = await ConnectionRecord.retrieve_by_id(context, connection_id)
    except StorageNotFoundError:
        raise web.HTTPNotFound()

    if connection.is_ready:
        msg = Ping()
        await outbound_handler(msg, connection_id=connection_id)

        await connection.log_activity(context, "ping", connection.DIRECTION_SENT)

    return web.json_response({})

from ..serializer import MessageSerializer
from ..connections.manager import ConnectionManager

@docs(tags=["trustping"], summary="Retrieve the trustping message.")
async def connections_send_ping_v2(request: web.BaseRequest):
    """
    Request handler for retrieving the trust ping message for a connection.

    Args:
        request: aiohttp request object

    """
    context = request.app["request_context"]
    connection_id = request.match_info["id"]
    outbound_handler = request.app["outbound_message_router_get_encoded_messages"]

    try:
        connection = await ConnectionRecord.retrieve_by_id(context, connection_id)
    except StorageNotFoundError:
        raise web.HTTPNotFound()

    connection_mgr = ConnectionManager(context)
    target = await connection_mgr.get_connection_target(connection)

    if connection.is_ready:
        msg = Ping()
        message = await outbound_handler(msg, connection_id=connection_id)
        if message.connection_id and not message.target:
            message.target = target

        # get a serializer and encode the message
        message_serializer = await context.inject(MessageSerializer)
        if not message.encoded and message.target:
            target = message.target
            message.payload = await message_serializer.encode_message(
                context,
                message.payload,
                target.recipient_keys or [],
                # (not direct_response) and target.routing_keys or [],
                [],
                target.sender_key,
            )
            message.encoded = True
        
        await connection.log_activity(context, "ping", connection.DIRECTION_SENT)

    # return the message as text
    return web.Response(text=message.payload.decode("utf-8"))

async def register(app: web.Application):
    """Register routes."""

    app.add_routes(
        [
            web.post("/connections/{id}/send-ping", connections_send_ping),
            web.post("/connections/{id}/send-ping-v2", connections_send_ping_v2),
        ]
    )
