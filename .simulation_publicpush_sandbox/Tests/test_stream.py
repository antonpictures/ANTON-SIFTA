import asyncio

async def test():
    try:
        cmd = ["python3", "-u", "sifta_arena.py", "--red", "qwen3.5:0.8b", "--blue", "deepseek-coder:1.3b", "--level", "1"]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        while True:
            line = await process.stdout.readline()
            if not line: break
            print("got:", line.decode()[:20])
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    asyncio.run(test())
