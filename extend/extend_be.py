from dat import get_ck

import httpx

import aiosqlite
import asyncio
import pickle
import datetime as dt

# with open("shib_be.pkl", 'rb') as file:
#     be = pickle.load(file)
#     # be = {'name':'s', 'value':'y'}

headers = {
    "X-Requested-With": "XMLHttpRequest"
}
transport = httpx.AsyncHTTPTransport(retries=3)

async def extendBe(client):
    res = await client.post("https://be.my.ucla.edu/IWE/Timeout.aspx/Extend", json={})
    # print(res.text)
    try:
        return res.json()["d"]['success']
    except:
        with open("extend/data/be_res.txt", 'w', encoding='utf-8') as file:
            file.write(res.text)
    return False


async def extend_loop_be():
    #only worksfor 4 hours, the max that my.ucla apache allows ig
    conn = await aiosqlite.connect("data/test.db")
    conn.row_factory = aiosqlite.Row
    works = True
    while works:
        cook = await get_ck(conn, 'shib.be')
        print(cook)
        assert cook is not None
        async with httpx.AsyncClient(cookies={cook['name']:cook['value']},
                                  headers=headers,
                                  transport=transport) as client:
            res = await extendBe(client)
            if not res:
                break
            print(f'extended be session:\ntime: {dt.datetime.now()}')
            await asyncio.sleep(60)
    print(f"stopped be at {dt.datetime.now()}")
    return "stopped"

asyncio.run(extend_loop_be())