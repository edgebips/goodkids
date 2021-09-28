#!/usr/bin/env python3
"""Experiment getting quotes using TW's websocket.

Please do not abuse this. Use this sparingly, e.g., for monitoring, and with
rate limiting.
"""

from typing import Optional
import json

import asyncio
import websockets
import click

from goodkids import session as sesslib


async def connect(tokens: dict[str, str]):
    uri = "wss://tasty-live-web.dxfeed.com/live/cometd"
    pp(tokens)
    streamer_url = tokens['streamer-url']
    #uri = f"ws://{streamer_url}"
    #uri = tokens['websocket-url']
    print(uri)
    async with websockets.connect(uri) as websocket:
        print("Connected")

        handshake = {
            "ext": {
                "com.devexperts.auth.AuthToken": tokens['token'],
            },
            "id": "1",
            "version": "1.0",
            "minimumVersion": "1.0",
            "channel": "/meta/handshake",
            "supportedConnectionTypes": ["websocket", "long-polling", "callback-polling"],
            "advice": {
                "timeout": 60000,
                "interval": 0,
            },
        }

        await websocket.send(json.dumps(handshake).encode('utf8'))
        print('a')
        message = await websocket.recv()
        print(message)

        # index = 0
        # async for message in websocket:
        #     print(index)
        #     index += 1
        #     pp(message)



@click.command()
@click.option('--username', '-u', help="Tastyworks username.")
@click.option('--password') # Tastyworks password.
def main(username: Optional[str], password: Optional[str]):
    # Get the account.
    session = sesslib.get_session(username, password)

    ##resp = session.relget('/option-chains/AAPL/nested')
    resp = session.relget('/quote-streamer-tokens')
    tokens = resp.json()['data']

    # func GetStreamerToken(authToken string) (*resty.Response, error) {
    # 	resp, err := resty.R().
    # 		SetHeader("Content-Type", "application/json").
    # 		SetHeader("Accept-Version", "v1").
    # 		SetHeader("Authorization", authToken).
    # 		Get("https://api.tastyworks.com/quote-streamer-tokens")

    # 	return resp, err


    asyncio.get_event_loop().run_until_complete(connect(tokens))





if __name__ == '__main__':
    main()
