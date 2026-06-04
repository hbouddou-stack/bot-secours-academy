import aiohttp
import asyncio
import json

async def test_api():
    async with aiohttp.ClientSession() as session:
        # test get admin reports
        async with session.post('http://localhost:8082/admin/reports', json={'userId': 2045194295}) as resp:
            data = await resp.json()
            print("Reports:", len(data.get('reports', [])))
            if data.get('reports'):
                print("First report academicYear:", data['reports'][0].get('academicYear'))

        # test get admin tickets
        async with session.post('http://localhost:8082/admin/tickets', json={'userId': 2045194295}) as resp:
            data = await resp.json()
            print("Tickets:", len(data.get('tickets', [])))
            if data.get('tickets'):
                print("First ticket academicYear:", data['tickets'][0].get('academicYear'))

if __name__ == '__main__':
    asyncio.run(test_api())
