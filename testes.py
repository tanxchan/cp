from pwsa import logon

from playwright.async_api import async_playwright
from playwright.async_api import expect
from dat import add_ck, get_ck
import pandas as pd
import httpx

import aiosqlite
import os
import json
import pickle
from datetime import datetime as dt
import asyncio

async def loop():
    #brute force keep idp alive
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        while True:
            cx = await browser.new_context(storage_state="data/cooking.json")
            page = await cx.new_page()
            await page.goto("https://be.my.ucla.edu")
            await expect(page).to_have_url("https://be.my.ucla.edu/studylist.aspx")
            c = await cx.cookies()
            assert c[0]
            shib_be = [i.get('value') for i in c if 
                   i.get("name") == "_shibsession_64656661756c7468747470733a" \
                   "2f2f62652e6d792e75636c612e6564752f73686962626f6c6574682d73702f"]
            print(f"found key {shib_be[0]} at {dt.now()}")
            await cx.close()
            await asyncio.sleep(60)


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await logon(page, "https://sa.ucla.edu/ro/ClassSearch")
        await context.storage_state(path="data/cooking.json")
        await page.close()
    await loop()
        
        

if __name__ == "__main__":
    asyncio.run(main())