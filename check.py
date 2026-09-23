from playwright.async_api import async_playwright
from playwright.async_api import expect
import pandas as pd
import httpx
from pwsa import get_searchkey, getTierData, get_cookies
from dat import get_ck

import aiosqlite
import os
import json
import pickle
import time
import datetime
import asyncio

delay = 60
ready = asyncio.Event()
sk = None
shib, iwe = None, None


async def loop():
    global sk
    global shib
    global iwe 
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(storage_state="data/cooked.json")
        # print(await context.cookies())
        await context.clear_cookies(name="_shibsession_64656661756c7468747470733a2f2f626" \
        "52e6d792e75636c612e6564752f73686962626f6c6574682d73702f")
        #make it generate a new one
        page = await context.new_page()
        while True:
            await page.goto("https://be.my.ucla.edu/")
            await expect(page).to_have_url("https://be.my.ucla.edu/studylist.aspx")
            await page.goto("https://be.my.ucla.edu/ClassPlanner/ClassPlan.aspx")
            await expect(page).to_have_url("https://be.my.ucla.edu/ClassPlanner/ClassPlan.aspx")
            sk = await get_searchkey(page)
            shib, iwe = await get_cookies(context)
            print(shib, iwe)
            await page.goto("about:blank")
            ready.set()
            await asyncio.sleep(delay)

async def checks():
    await ready.wait()
    # conn = await aiosqlite.connect("data/test.db")
    # conn.row_factory = aiosqlite.Row
    # shib = await get_ck(conn, "shib.be")
    # iwe = await get_ck(conn, "iwe.26F")
    if not (shib and iwe):
        print("no cookies?")
        print(shib, iwe)
        return
    print("cookies!")
    async with httpx.AsyncClient(cookies={i['name']:i['value'] for i in [shib, iwe]}) as client:
        while True:
            await getTierData(client, "MATH", "0032A", sk, "26F")
            print(f"checked at {datetime.datetime.now()}")
            await asyncio.sleep(10)

async def main():
    await asyncio.gather(loop(), checks())
if __name__ == '__main__':
    asyncio.run(main())