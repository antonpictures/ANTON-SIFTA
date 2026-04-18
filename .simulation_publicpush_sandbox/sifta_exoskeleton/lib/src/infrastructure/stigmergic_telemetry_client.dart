import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// Pattern A: watch `.sifta_state/` and re-read overlay + JSONL tails.
/// Uses **directory** `watch` (required on Windows; reliable on macOS/Linux).
class StigmergicTelemetryClient {
  StigmergicTelemetryClient(this.stateDir);

  final Directory stateDir;

  File get _fitnessFile => File('${stateDir.path}/memory_fitness.json');
  File get _ideTraceFile => File('${stateDir.path}/ide_stigmergic_trace.jsonl');
  File get _telemetrySnapshotFile =>
      File('${stateDir.path}/telemetry_snapshot.json');

  Duration debounce = const Duration(milliseconds: 120);

  Stream<void> _debouncedDirEvents() async* {
    if (!await stateDir.exists()) {
      return;
    }
    await for (final _ in stateDir.watch(events: FileSystemEvent.all)) {
      await Future<void>.delayed(debounce);
      yield;
    }
  }

  /// Full parse of `memory_fitness.json` (nested `traces` schema supported).
  Stream<Map<String, dynamic>> watchMemoryFitness() async* {
    yield await readMemoryFitnessSnapshot();
    await for (final _ in _debouncedDirEvents()) {
      yield await readMemoryFitnessSnapshot();
    }
  }

  /// Unified organism vitals from `telemetry_snapshot.json` (Python writer).
  /// Same directory debounce as other streams — one coherent refresh tick.
  Stream<Map<String, dynamic>> watchTelemetrySnapshot() async* {
    yield await readTelemetrySnapshot();
    await for (final _ in _debouncedDirEvents()) {
      yield await readTelemetrySnapshot();
    }
  }

  Future<Map<String, dynamic>> readMemoryFitnessSnapshot() async {
    return _readJsonFile(_fitnessFile);
  }

  Future<Map<String, dynamic>> readTelemetrySnapshot() async {
    return _readJsonFile(_telemetrySnapshotFile);
  }

  Future<Map<String, dynamic>> _readJsonFile(File f) async {
    if (!await f.exists()) {
      return <String, dynamic>{};
    }
    try {
      final txt = await f.readAsString();
      if (txt.trim().isEmpty) {
        return <String, dynamic>{};
      }
      final decoded = jsonDecode(txt);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
      return <String, dynamic>{};
    } catch (_) {
      return <String, dynamic>{};
    }
  }

  /// Last [tailCount] JSON objects from `ide_stigmergic_trace.jsonl` (newest last).
  Stream<List<Map<String, dynamic>>> watchIdeTraces({int tailCount = 24}) async* {
    yield await tailIdeTrace(tailCount: tailCount);
    await for (final _ in _debouncedDirEvents()) {
      yield await tailIdeTrace(tailCount: tailCount);
    }
  }

  Future<List<Map<String, dynamic>>> tailIdeTrace({int tailCount = 24}) async {
    final f = _ideTraceFile;
    if (!await f.exists()) {
      return <Map<String, dynamic>>[];
    }
    try {
      final lines = await f.readAsLines();
      if (lines.isEmpty) {
        return <Map<String, dynamic>>[];
      }
      final start = lines.length > tailCount ? lines.length - tailCount : 0;
      final out = <Map<String, dynamic>>[];
      for (var i = start; i < lines.length; i++) {
        final line = lines[i].trim();
        if (line.isEmpty) {
          continue;
        }
        try {
          final row = jsonDecode(line);
          if (row is Map<String, dynamic>) {
            out.add(row);
          }
        } catch (_) {
          // concurrent append half-line — skip
        }
      }
      return out;
    } catch (_) {
      return <Map<String, dynamic>>[];
    }
  }

  Future<void> dispose() async {}
}
