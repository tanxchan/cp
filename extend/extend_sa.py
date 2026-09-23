from dat import get_ck

import httpx

import aiosqlite
import asyncio
import pickle
import datetime as dt

headers = {
    "X-Requested-With": "XMLHttpRequest"
}
transport = httpx.AsyncHTTPTransport(retries=3)

# with open("shib_sa.pkl", 'rb') as file:
#     sa = pickle.load(file)

async def extendSa(client):
    res = await client.get("https://sa.ucla.edu/ro/ClassSearch/Search/KeepServerAlive")
    # print(res.text)
    if "ServerAliveResponse" in res.text:
        return True
    with open("extend/data/sa_res.txt", 'w', encoding='utf-8') as file:
        file.write(res.txt)
    return False

async def extend_loop_sa():
    conn = await aiosqlite.connect("data/test.db")
    conn.row_factory = aiosqlite.Row
    cook = await get_ck(conn, 'shib.be')
    print(cook)
    assert cook is not None
    async with httpx.AsyncClient(cookies={cook['name']:cook['value']},
                                  headers=headers,
                                  transport=transport) as client:
        works = True
        while works:
            res = await extendSa(client)
            if not res:
                break
            print(f'extended sa session:\ntime: {dt.datetime.now()}')
            await asyncio.sleep(600)
    print(f"stopped sa at {dt.datetime.now()}")
    return "stopped"

def main():
    asyncio.run(extend_loop_sa())

if __name__ == "__main__":
    main()