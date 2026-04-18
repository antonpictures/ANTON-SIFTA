import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'src/providers/telemetry_providers.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: SiftaExoskeletonApp()));
}

class SiftaExoskeletonApp extends StatelessWidget {
  const SiftaExoskeletonApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SIFTA Exoskeleton',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF00ffc8),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: const TelemetryDashboard(),
    );
  }
}

class TelemetryDashboard extends ConsumerWidget {
  const TelemetryDashboard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final snap = ref.watch(telemetrySnapshotProvider);
    final fit = ref.watch(memoryFitnessProvider);
    final ide = ref.watch(ideTraceProvider);
    final statePath = ref.watch(siftaStateDirProvider);

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('SIFTA — Pattern A dirt'),
            Text(
              statePath,
              style: TextStyle(
                fontSize: 11,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                fontFamily: 'monospace',
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Text('SIFTA_STATE_DIR', style: Theme.of(context).textTheme.titleSmall),
          SelectableText(
            const String.fromEnvironment('SIFTA_STATE_DIR', defaultValue: '')
                    .isEmpty
                ? '(unset — using relative fallback; prefer --dart-define)'
                : const String.fromEnvironment('SIFTA_STATE_DIR'),
            style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
          ),
          const SizedBox(height: 16),
          Text('telemetry_snapshot.json', style: Theme.of(context).textTheme.titleMedium),
          snap.when(
            data: (m) => _SnapshotBody(map: m),
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text('Error: $e'),
          ),
          const SizedBox(height: 24),
          Text('memory_fitness.json', style: Theme.of(context).textTheme.titleMedium),
          fit.when(
            data: (m) => _FitnessBody(map: m),
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text('Error: $e'),
          ),
          const SizedBox(height: 24),
          Text('ide_stigmergic_trace.jsonl (tail)', style: Theme.of(context).textTheme.titleMedium),
          ide.when(
            data: (rows) => _IdeTail(rows: rows),
            loading: () => const LinearProgressIndicator(),
            error: (e, _) => Text('Error: $e'),
          ),
        ],
      ),
    );
  }
}

class _SnapshotBody extends StatelessWidget {
  const _SnapshotBody({required this.map});

  final Map<String, dynamic> map;

  @override
  Widget build(BuildContext context) {
    if (map.isEmpty) {
      return const Text('(no snapshot — run System/telemetry_snapshot.py)');
    }
    final iso = map['snapshot_iso'];
    final lam = map['manifold'];
    final meta = map['metabolism'];
    final gn = map['graveyard'];
    final ld = map['ledger'];
    final ppo = map['ppo_entropy_bridge'];
    final tes = map['stigmergic_entropy_trace_summary'];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('snapshot: $iso', style: const TextStyle(fontFamily: 'monospace')),
        if (lam is Map) Text('λ_norm: ${lam['lambda_norm']}'),
        if (meta is Map)
          Text('metabolism: ${meta['regime']} · mint ${meta['mint_rate']} · store ${meta['store_fee']}'),
        if (ppo is Map)
          Text(
            'PPO c₂: ${ppo['entropy_coefficient_c2']} · headroom ${ppo['exploration_headroom']} (${ppo['schedule']})',
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
        if (tes is Map && tes['events_loaded'] != null && (tes['events_loaded'] as num) > 0)
          Text(
            'Trace c₂: ${tes['trace_entropy_coefficient_c2']} · events ${tes['events_loaded']}',
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
        if (gn is Map) Text('graveyard: ${gn['total_deaths']} deaths'),
        if (ld is Map) Text('ledger: ${ld['total_memories']} memories'),
      ],
    );
  }
}

class _FitnessBody extends StatelessWidget {
  const _FitnessBody({required this.map});

  final Map<String, dynamic> map;

  @override
  Widget build(BuildContext context) {
    if (map.isEmpty) {
      return const Text('(empty or unreadable — is Python writing overlay?)');
    }
    final rawTraces = map['traces'];
    if (rawTraces is! Map) {
      return SelectableText(const JsonEncoder.withIndent('  ').convert(map));
    }
    final entries = rawTraces.entries.toList()
      ..sort((a, b) {
        num f(MapEntry<dynamic, dynamic> e) {
          final v = e.value;
          if (v is Map && v['fitness'] is num) {
            return v['fitness'] as num;
          }
          return 0;
        }

        return f(b).compareTo(f(a));
      });
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final e in entries.take(12))
          ListTile(
            dense: true,
            title: Text(e.key, style: const TextStyle(fontFamily: 'monospace')),
            subtitle: Text(
              e.value is Map ? (e.value as Map).toString() : '$e.value',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
      ],
    );
  }
}

class _IdeTail extends StatelessWidget {
  const _IdeTail({required this.rows});

  final List<Map<String, dynamic>> rows;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) {
      return const Text('(no rows)');
    }
    final rev = rows.reversed.toList();
    return Column(
      children: [
        for (final r in rev.take(15))
          ListTile(
            dense: true,
            title: Text(
              '${r['source_ide'] ?? '?'} · ${r['kind'] ?? '?'}',
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
            subtitle: Text(
              '${r['payload'] ?? ''}'.replaceAll('\n', ' '),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
      ],
    );
  }
}
