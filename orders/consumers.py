from channels.generic.websocket import AsyncJsonWebsocketConsumer
class OrderConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.location_id = self.scope['url_route']['kwargs'].get('location_id','default')
        self.group = f"loc_{self.location_id}_orders"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)
    async def order_event(self, event):
        await self.send_json(event["data"])
