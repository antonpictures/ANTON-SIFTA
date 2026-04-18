import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../infrastructure/stigmergic_telemetry_client.dart';

/// Absolute path to `.sifta_state` — set via:
/// `flutter run --dart-define=SIFTA_STATE_DIR=/path/to/ANTON_SIFTA/.sifta_state`
final siftaStateDirProvider = Provider<String>((ref) {
  const fromEnv = String.fromEnvironment('SIFTA_STATE_DIR', defaultValue: '');
  if (fromEnv.isNotEmpty) {
    return fromEnv;
  }
  // Dev fallback: run `flutter run` from `sifta_exoskeleton/` with repo layout sibling.
  return Directory.current.path.contains('sifta_exoskeleton')
      ? '${Directory.current.path}/../.sifta_state'
      : '${Directory.current.path}/.sifta_state';
});

final telemetryClientProvider = Provider<StigmergicTelemetryClient>((ref) {
  final p = ref.watch(siftaStateDirProvider);
  return StigmergicTelemetryClient(Directory(p));
});

final memoryFitnessProvider =
    StreamProvider<Map<String, dynamic>>((ref) async* {
  final client = ref.watch(telemetryClientProvider);
  await for (final m in client.watchMemoryFitness()) {
    yield m;
  }
});

final ideTraceProvider =
    StreamProvider<List<Map<String, dynamic>>>((ref) async* {
  final client = ref.watch(telemetryClientProvider);
  await for (final rows in client.watchIdeTraces()) {
    yield rows;
  }
});

/// Single-file organism view (Antigravity `telemetry_snapshot.py` → dirt).
final telemetrySnapshotProvider =
    StreamProvider<Map<String, dynamic>>((ref) async* {
  final client = ref.watch(telemetryClientProvider);
  await for (final m in client.watchTelemetrySnapshot()) {
    yield m;
  }
});
