from collections import namedtuple
import inspect


def test_wellbeing_cortex_runs_without_psutil(monkeypatch):
    from System import swarm_wellbeing_cortex as cortex_mod

    monkeypatch.setattr(cortex_mod, "_psutil", None)

    def fake_check_output(cmd, **_kwargs):
        if cmd == ["sysctl", "-n", "hw.memsize"]:
            return str(4096 * 100)
        if cmd == ["vm_stat"]:
            return (
                "Mach Virtual Memory Statistics: (page size of 4096 bytes)\n"
                "Pages free:                               25.\n"
                "Pages speculative:                         0.\n"
            )
        if cmd == ["pmset", "-g", "batt"]:
            return "Now drawing from 'AC Power'\n -InternalBattery-0 88%; charging;"
        if cmd == ["pmset", "-g", "therm"]:
            return "CPU_Speed_Limit = 100\n"
        raise AssertionError(f"unexpected command: {cmd}")

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(cortex_mod.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(cortex_mod.shutil, "disk_usage", lambda _path: Usage(total=100, used=25, free=75))

    cortex = cortex_mod.SwarmWellbeingCortex.__new__(cortex_mod.SwarmWellbeingCortex)
    hw = cortex.get_hardware_state()

    assert hw["memory_usage_percent"] == 75.0
    assert hw["disk_usage_percent"] == 25.0
    assert hw["battery_percent"] == 88.0
    assert hw["power_plugged"] is True
    assert hw["thermal_pressure"] == "Normal"


def test_control_center_glass_widget_can_be_manifest_instantiated():
    from Applications.sifta_control_center import GlassWidget

    sig = inspect.signature(GlassWidget)
    assert sig.parameters["x"].default is None
    assert sig.parameters["y"].default is None
