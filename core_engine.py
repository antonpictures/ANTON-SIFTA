import asyncio
from rich.console import Console
from sifta_cardio import async_jellyfish_loop
from sifta_swarm_identity import async_identity_watchdog

console = Console()

async def hermes_heartbeat():
    """The Scheduler: Fires independently, never blocking the Queen."""
    console.print("[bold yellow][HERMES] ⚡ Pulse active. Sweeping for dead-drops via Cardio...[/bold yellow]")
    try:
        await async_jellyfish_loop()
    except Exception as e:
        console.print(f"[bold red][HERMES FATAL] {e}[/bold red]")

async def identity_guardian():
    """Continuous Integrity Watchdog running natively on the async queue."""
    console.print("[bold magenta][IDENTITY] 🧬 Hardware Integrity lock engaged.[/bold magenta]")
    try:
        await async_identity_watchdog(interval=5.0)
    except Exception as e:
        console.print(f"[bold red][IDENTITY FATAL] {e}[/bold red]")

async def m1ther_listener():
    """The Queen: Always listening for local/remote WORMHOLE breaches."""
    import uvicorn
    from server import app as m1ther_app
    
    console.print("[bold cyan][M1THER] 👑 Watchtower active. Securing inbound REST architecture (Port 8000).[/bold cyan]")
    # Run Uvicorn natively inside the single OS thread asyncio loop.
    config = uvicorn.Config(m1ther_app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()

async def swarm_kernel_boot():
    """The Bare-Metal OS Event Loop."""
    console.print("[bold green]/// BOOTING NON-BLOCKING SIFTA KERNEL ///[/bold green]")
    
    # asyncio.gather runs all Swarm agents simultaneously on one thread
    await asyncio.gather(
        m1ther_listener(),
        identity_guardian(),
        hermes_heartbeat()
    )

if __name__ == "__main__":
    try:
        # The absolute lowest-level execution command
        asyncio.run(swarm_kernel_boot())
    except KeyboardInterrupt:
        console.print("\n[bold red]/// KERNEL HALTED BY ARCHITECT ///[/bold red]")
