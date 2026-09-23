from playwright.async_api import async_playwright
from playwright.async_api import expect
from dat import add_ck, get_ck
import pandas as pd
import httpx

import aiosqlite
import os
import json
import pickle
import time
import asyncio



async def logon(page, i = "", o = None):
    #log on to be, use cookiese if necessary
    if i:
    #     async with page.expect_navigation(wait_until="domcontentloaded"):
        await page.goto(i)
    if page.url.startswith(r"https://shb"):
        print("logging in... wait for duo")
        # await page.locator("#logon").fill(LOGON)
        # await page.locator("#pass").fill(PW)
        # await page.locator('button[name="_eventId_proceed"]').click()
        await asyncio.sleep(1)
    if o:
        return await expect(page).to_have_url(o, timeout=30*1000)
    else:
        return await expect(page).to_have_url(i, timeout=30*1000)

async def get_cookies(context):
    shib = {}
    iwe = {}
    cookies = await context.cookies()
    for cookie in cookies:
        if cookie["name"].startswith("_shibsession_"):
            shib = cookie
        elif cookie["name"].startswith("iwe_term_enrollment"):
            iwe = cookie
    return (shib, iwe)

async def get_searchkey(page):
    #super slow either way probably
    await page.locator("#searchTier0").click()#fill("Mathematics (MATH)")
    menu = page.locator("ul.ui-autocomplete:visible")
    await expect(menu).to_be_visible()
    await menu.get_by_text( 
        "Mathematics (MATH)",
        exact=False
    ).click()
    # await page.locator("#searchTier0").press("Enter")
    await page.locator("#searchTier1").click()#fill("32A - Calculus of Several Variables")
    menu = page.locator("ul.ui-autocomplete:visible")
    await expect(menu).to_be_visible()
    await menu.get_by_text(
        "32A - Calculus of Several Variables",
        exact=False
    ).click()
    # await page.keyboard.press("Tab")
    # await page.keyboard.press("Enter")
    # await asyncio.sleep(5)
    await page.locator("#ctl00_MainContent_cs_goButton").click()
    # await page.locator("#ctl00_MainContent_cs_goButton").press("Enter")
    # await asyncio.sleep(5)
    await expect(page.locator('[name="ctl00$MainContent$cs$key2"]')).not_to_have_value("")
    return await page.locator('[name="ctl00$MainContent$cs$key2"]').get_attribute('value')

async def getTierData(client, subject, catalog, searchKey, quarter):
    url = "https://be.my.ucla.edu/ClassPlanner/ClassSearch.asmx/getTierData"
    payload = {
        "search_by_typ_cd": "subject",
        "term_cd": quarter,#must match that within session
        "ses_grp_cd": "%",
        "subj_area_cd": subject,#leading spaces are ignored
        "crs_catlg_no": catalog,#leading spaces are ignored, leading 0s are not. must be padded to 4
        "class_no": "%",
        "class_id": "%",
        "class_units": "%",
        "honors_type_cd": "%",
        "instr_nm": "%",
        "act_enrl_seq_num": "%",
        "active_enrl_fl": "y",
        "class_prim_act_fl": "y",
        "id": "hn5pd4RQd7Itf0a3GvcnS88IfBNwrz0V+TSxWi6dB6c=",#not important, any working key always works
        "searchKey": searchKey#really annoying to find, comes from ClassPlan.aspx
        #however, unclear as to how to obtain
    }
    response = await client.post(url, json=payload)

    # print("Response code: ", response.status_code)

    data = response.json()
    rows = data["d"]["svcRes"]["ResultTiers"]
    df = pd.DataFrame(rows)[[
        "class_section",
        "instr_info",
        "meet_days",
        "meet_times",
        "meet_location",
        "enrl_status",
        "finl_day",
        "finl_date",
        "finl_times",
        "srs_crs_no",
        "unt_range"
    ]]
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    df["enrl_status"] = df["enrl_status"].str.extract(r"</i>(.*)$")
    df["start_time"] = df["meet_times"].str.extract(r"^(.*)<")
    df["end_time"] = df["meet_times"].str.extract(r"-(.*)$")
    df.drop(inplace = True, columns = ["meet_times"])
    return df

async def drop(client, termCode, classID):
    #pretty sure that the 01 is just the discussion and 00 is always the lecture
    url = "https://sa.ucla.edu/ro/ClassSearch/Enrollment/DropClass"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; char=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }
    data = {
        "termCode": termCode,
        "classId": classID, 
        "classIdsForClassDropExchange": f"{classID[:-2] + "00"},{classID}",
    }
    response = await client.post(
        url,
        headers=headers,
        data=data,
    )
    return "You have successfully dropped" in response.text

async def enroll(client, classId, subj, catalog, termCode="26F"):
    # pretty sure that the 01 is just the discussion and 00 is always the lecture
    lectureId = classId[:-2] + "00"
    url = "https://sa.ucla.edu/ro/ClassSearch/Enrollment/EnrollAClass"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
    }
    data = {
        "TermCode": termCode,
        "CourseNumber": classId,
        "AdditionalCourseNumber": None,
        "ConflictOverride": None,
        "PteNumber": None,      
        "UnitsAttempted": [None],
        "Waitlist": "",
        "GradeType": "LG",
        "GradeTypeID": lectureId,
        "SubjectArea": subj,
        "CrsCatalogNo": catalog,
        "ClassIDInput": f"{classId},{lectureId}",
        "Path": f"{classId}_{lectureId}_{subj.strip()}{catalog.strip()}",
        "ActionType": "enroll",
    }
    response = await client.get(
        url,
        headers=headers,
        params={
            "input": json.dumps(data, separators=(",", ":")),
            "_": int(time.time() * 1000),
        },
    )
    return "You have successfully enrolled" in response.text

async def main():
    conn = await aiosqlite.connect("data/test.db")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            with open("shib_be.pkl", 'rb') as file:
                shib = pickle.load(file)
                await page.context.add_cookies([shib])
        except Exception as e:
            print(f"No/invalid Be cookie: {e}")
        await logon(page, r"https://be.my.ucla.edu", r"https://be.my.ucla.edu/studylist.aspx")
        await page.goto("https://be.my.ucla.edu/ClassPlanner/ClassPlan.aspx")
        shibBe, iwe = await get_cookies(context)
        print(iwe)
        if shibBe:
            with open('shib_be.pkl', 'wb') as file:
                pickle.dump(shibBe, file)
        await add_ck(conn, shibBe)
        await add_ck(conn, iwe)
        sk = await get_searchkey(page)
        # print(await context.cookies())
        # await asyncio.sleep(10)
        try:
            with open("shib_sa.pkl", 'rb') as file:
                shibSa = pickle.load(file)
                await page.context.add_cookies([shibSa])
        except Exception as e:
            print(f"No/invalid SA cookie: {e}")
        await context.storage_state(path="data/cooked.json")
        await page.goto(r"https://sa.ucla.edu/ro/ClassSearch/Enrollment")
        await expect(page).to_have_url(r"https://sa.ucla.edu/ro/ClassSearch/Enrollment")
        shibSa, iwe2 = await get_cookies(context)
        if shibSa:
            with open('shib_sa.pkl', 'wb') as file:
                pickle.dump(shibSa, file)
        await add_ck(conn, shibSa)
        print(shibSa)
        # await asyncio.sleep(10)
    cookies = [shibSa, shibBe, iwe]
    async with httpx.AsyncClient(cookies={i['name']:i['value'] for i in cookies}) as client:
        print(await getTierData(client, "MATH", "0032A", sk, "26F"))
        pass
    await conn.commit()

    # async with async_playwright() as playwright:
    #     browser = await playwright.chromium.launch(headless=False)
    #     context = await browser.new_context(storage_state="data/cooked.json")
    #     await context.clear_cookies(name="_shibsession_64656661756c7468747470733a2f2f62652e6d792e75636c612e6564752f73686962626f6c6574682d73702f")
    #     page = await context.new_page()
    #     url = "https://sa.ucla.edu/ro/ClassSearch"
    #     await page.goto(url)
    #     await expect(page).to_have_url(url)
    #     await page.goto("https://sa.ucla.edu/ro/ClassSearch")
    #     print(await context.cookies())
        # print(await page.content())


# cook = [{'name': '__Host-JSESSIONID', 'value': '0524892D07DFE327985382C4515A44FB', 'domain': 'shb.ais.ucla.edu', 'path': '/', 'expires': -1, 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}, 
#         {'name': 'cppsvWCwsHiQXFwCnBKv5jPJGqJCpw__', 'value': 'v1PgVPCe+Cghs', 'domain': 'shb.ais.ucla.edu', 'path': '/', 'expires': -1, 'httpOnly': False, 'secure': True, 'sameSite': 'None'}, 
#         # {'name': 'auth-sid-c', 'value': '"NTc3ZWQ3ZTQzZjY0NDJiZGI0ZjJkNDlmZmQ3MDQ4MjY=|1789356418|32dfdb0ffb9b6b61c1386ba52c9c3fb3062c986a"', 'domain': 'api-d594f029.duosecurity.com', 'path': '/', 'expires': -1, 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}, 
#         # {'name': 'auth-sid-c-init-eebabdc6f4d1498e8bb07d55138ec9f7', 'value': '"NTc3ZWQ3ZTQzZjY0NDJiZGI0ZjJkNDlmZmQ3MDQ4MjY=|1789356418|cbb83a5353f9f87a3da011c6e91a22550f283d95"', 'domain': 'api-d594f029.duosecurity.com', 'path': '/', 'expires': -1, 'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}, 
#         # {'name': 'trc|DUO691FJLZQ2SRZJAEJD|DADOXLPCIE8FZM8Y6CJ9', 'value': 'EPI400FL1WLTHRT6UJ35', 'domain': 'api-d594f029.duosecurity.com', 'path': '/', 'expires': 1823916424.857194, 'httpOnly': True, 'secure': True, 'sameSite': 'None'}, 
#         # {'name': 'lam|DIFIXX6CCZ5A9P1Y0SPI|DUO691FJLZQ2SRZJAEJD', 'value': 'Duo_Push|DPXACTIBLZSDHPCUXTP2','domain': 'api-d594f029.duosecurity.com', 'path': '/', 'expires': 1820892424.857452, 'httpOnly': True, 'secure': True, 'sameSite': 'None'}, 
#         # {'name': 'hac|DUO691FJLZQ2SRZJAEJD|DADOXLPCIE8FZM8Y6CJ9', 'value': '"MTc4OTM1NjQyNA==|1789356424|6c12ddc20caa03491a055b66160a1e2f55715f92"', 'domain': 'api-d594f029.duosecurity.com', 'path': '/', 'expires': 1823916424.857522, 'httpOnly': True, 'secure': True, 'sameSite': 'None'}, 
#         {'name': '__Host-shib_idp_session', 'value': '03994a4849b8fdc8c632a1c6af5a4e2551d3ab527e670a1234ee89c853064a66', 'domain': 'shb.ais.ucla.edu', 'path': '/', 'expires': -1,'httpOnly': True, 'secure': True, 'sameSite': 'Lax'}, 
#         # {'name': '_shibsession_64656661756c7468747470733a2f2f62652e6d792e75636c612e6564752f73686962626f6c6574682d73702f', 'value': '_985d72e9beb0c5d9fcb23ad2175e13c9', 'domain': 'be.my.ucla.edu', 'path': '/', 'expires': -1, 'httpOnly': True, 'secure': False, 'sameSite': 'Lax'}, 
#         # {'name': 'ASP.NET_SessionId', 'value': 'qf1gqfivrmkzhkgsygc1dcyr', 'domain': 'be.my.ucla.edu', 'path': '/', 'expires':-1, 'httpOnly': True, 'secure': False, 'sameSite': 'Lax'}, 
#         # {'name': 'SameSite', 'value': 'None', 'domain': 'be.my.ucla.edu', 'path': '/', 'expires': 1789356458.606006, 'httpOnly': False, 'secure': False, 'sameSite': 'Lax'}, 
#         # {'name': '_ga', 'value': 'GA1.1.574434953.1789356429', 'domain': '.ucla.edu', 'path': '/', 'expires': 1823916429.830234, 'httpOnly': False, 'secure': False, 'sameSite': 'Lax'}, 
#         # {'name': 'iwe_term_enrollment_urn%3amace%3aucla.edu%3appid%3aperson%3aFF27DFC0E4DF453EA084BF0E3728E4EB', 'value': '26F', 'domain': '.ucla.edu', 'path': '/', 'expires': -1, 'httpOnly': False,'secure': False, 'sameSite': 'Lax'}, 
#         # {'name': '_ga_Y76YP787Q7', 'value': 'GS2.1.s1789356428$o1$g1$t1789356429$j59$l0$h0', 'domain': '.ucla.edu', 'path': '/', 'expires': 1823916429.83646, 'httpOnly': False, 'secure': False, 'sameSite': 'Lax'}
# ]
# async def test(browser, name):
#     context = await browser.new_context()
#     await context.add_cookies(cook)
#     if name:
#         await context.clear_cookies(name=name)
#     page = await context.new_page()
#     await page.goto(r"https://sa.ucla.edu/ro/ClassSearch/Enrollment")
#     await expect(page).to_have_url("https://sa.ucla.edu/ro/ClassSearch/Enrollment")

# async def testes():
#     async with async_playwright() as playwright:
#         browser = await playwright.chromium.launch(headless=True)
#         results = await asyncio.gather(
#             *[test(browser, cookie['name']) for cookie in cook], return_exceptions=True
#         )
#     for i, res in enumerate(results):
#         if isinstance(res, Exception):
#             print(f"{cook[i]['name']} is neccessary")
#         else:
#             print(f"{cook[i]['name']} is extraneous")
# async def test2():
#     async with async_playwright() as playwright:
#         browser = await playwright.chromium.launch(headless=False)
#         context = await browser.new_context()
#         await context.add_cookies(cook)
#         page = await context.new_page()
#         await page.goto(r"https://sa.ucla.edu/ro/ClassSearch/Enrollment")
#         await expect(page).to_have_url("https://sa.ucla.edu/ro/ClassSearch/Enrollment")
#         await asyncio.sleep(10)
# # print(asyncio.run(test(None)))
# # print(asyncio.run(testes()))
# asyncio.run(test2())

if __name__ == '__main__':
    asyncio.run(main())