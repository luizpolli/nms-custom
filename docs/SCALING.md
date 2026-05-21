# NMS_Custom — Scaling, HA & Multi-Cluster

Este documento describe cómo escalar NMS_Custom horizontalmente, cómo desplegar
una topología de Alta Disponibilidad (HA) y cómo extenderlo a un modelo
multi-cluster / multi-región.

> **Audiencia:** operadores de plataforma, SREs y arquitectos que despliegan
> NMS_Custom en producción Kubernetes.

---

## Tabla de Contenidos

1. [Objetivos de capacidad](#objetivos-de-capacidad)
2. [Modelo de escalado](#modelo-de-escalado)
3. [Topologías de despliegue](#topologías-de-despliegue)
4. [HA por componente](#ha-por-componente)
5. [Event bus: Redis Streams vs Kafka](#event-bus-redis-streams-vs-kafka)
6. [Sharding de workers](#sharding-de-workers)
7. [Multi-cluster / multi-región](#multi-cluster--multi-región)
8. [Capacity planning](#capacity-planning)
9. [Tuning y benchmarks](#tuning-y-benchmarks)
10. [Failure modes y recuperación](#failure-modes-y-recuperación)

---

## Objetivos de capacidad

Tres tallas de referencia que usamos para dimensionar el chart y los workers:

| Talla       | Dispositivos | KPIs / min | Traps / s | Réplicas API | Réplicas worker (cada uno) | DB IOPS |
|-------------|--------------|-----------:|----------:|-------------:|----------------------------:|--------:|
| **Small**   | 10–500       |    ~30 000 |        50 |            2 |                           1 |   1 000 |
| **Medium**  | 500–2 000    |   ~120 000 |       200 |            3 |                           2 |   5 000 |
| **Large**   | 2 000–5 000  |   ~300 000 |       500 |            4 |                           4 |  15 000 |
| **XLarge**  | 5 000–15 000 |   ~900 000 |     1 500 |            6 |                           8 |  40 000 |

> XLarge requiere **sharding** del poller y/o **federación** multi-cluster.
> Más allá de ~5 000 dispositivos por cluster, recomendamos partir el inventario
> por región o por technology y usar topología hub-and-spoke (ver §7).

---

## Modelo de escalado

### Stateless vs stateful

| Componente              | Stateless? | Estrategia                                          |
|-------------------------|:----------:|------------------------------------------------------|
| API (FastAPI)           | ✅         | HPA por CPU+memoria, ≥2 réplicas                    |
| Frontend (Nginx/Vite)   | ✅         | HPA por CPU, ≥2 réplicas                            |
| Worker poller           | ⚠️ shard   | HPA + `WORKER_SHARD_ID`/`SHARD_COUNT`               |
| Worker telemetry        | ⚠️ shard   | Consumer group (Redis Streams o Kafka)              |
| Worker alarm            | ⚠️ shard   | Consumer group con `XAUTOCLAIM` para reclamar stale |
| Worker discovery        | ❌         | Singleton + lease en Redis (`SETNX` con TTL)        |
| Worker report           | ✅         | HPA por queue depth                                 |
| Telemetry receiver gNMI | ✅         | HPA, service-type ClusterIP detrás de un LB         |
| Trap receiver SNMP UDP  | ⚠️ UDP     | DaemonSet o ≥2 réplicas con `externalTrafficPolicy: Local` |
| Postgres / TimescaleDB  | ❌         | Patroni o servicio gestionado (RDS, Aiven, Crunchy) |
| Redis                   | ❌         | Redis Sentinel o Redis Cluster (ver §5)             |
| Kafka (opcional)        | ❌         | 3 brokers + KRaft o Zookeeper                       |

### Reglas de oro

1. **Nunca menos de 2 réplicas** para algo que sirve tráfico (API, frontend, receiver).
2. **PodDisruptionBudget con `minAvailable: 1`** en todo lo que tenga ≥2 réplicas.
3. **`topologySpreadConstraints`** por zona para que un AZ no se lleve todas las réplicas.
4. **HPA con CPU + memoria** — los workers de telemetría son sensibles a RAM por buffering.
5. **Discovery worker corre como singleton** con lease distribuido — múltiples descubrimientos paralelos saturan la red.

---

## Topologías de despliegue

### 1. Single-cluster HA (default productivo)

```
                            ┌────────────────┐
                            │  Ingress NGINX  │ (≥2 réplicas, 2 AZs)
                            └────────┬───────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                    │
        ┌───────▼──────┐     ┌──────▼───────┐     ┌──────▼───────┐
        │ API replica 1│     │ API replica 2│     │ API replica 3│
        │   (zone-a)   │     │   (zone-b)   │     │   (zone-c)   │
        └───────┬──────┘     └──────┬───────┘     └──────┬───────┘
                │                    │                    │
                └─────────┬──────────┴─────────┬──────────┘
                          │                    │
            ┌─────────────▼──────────┐  ┌──────▼─────────────┐
            │ Postgres primary       │  │ Redis Sentinel (3) │
            │  + 1 sync replica      │  │  + 2 replicas      │
            │  + 1 async replica     │  │                    │
            └────────────────────────┘  └────────────────────┘
```

- 3 zonas de disponibilidad
- API + workers stateless distribuidos por `topologySpreadConstraints`
- DB primaria con réplica síncrona en otra AZ (RPO ≈ 0, RTO ≤ 60 s con failover)
- Redis Sentinel con 3 sentinels en AZs distintas

### 2. Multi-cluster federado (XLarge, geo-distribuido)

Ver §7 — un cluster por región + agregador central.

### 3. Edge / Air-gapped (compliance)

Mini-cluster on-prem por sitio (3 nodos K3s), espejo de imágenes, postgres
local. Sincronización periódica con central vía API HTTPS (push-only).

---

## HA por componente

### API & Frontend

```yaml
# values-prod.yaml
replicaCount:
  api: 3
  frontend: 2

autoscaling:
  api:
    enabled: true
    minReplicas: 3
    maxReplicas: 10

pdb:
  enabled: true
  minAvailable: 2  # tolera la caída de 1 pod sin perder quorum de servicio
```

- Probes: `/healthz` (liveness) y `/readyz` (readiness) — readiness valida DB+Redis
- `terminationGracePeriodSeconds: 30` para drenar conexiones WebSocket
- `preStop` hook que cierra el server FastAPI con SIGTERM y espera al pool

### Workers

Cada worker corre como **Deployment independiente** con su propio HPA y PDB.
Distribución entre réplicas vía consumer-group: cada réplica reclama un
subconjunto del stream (`XREADGROUP` + `XAUTOCLAIM`).

Para el **poller SNMP** la partición es por `device_id % SHARD_COUNT == SHARD_ID`
(ver §6). Para `alarm` y `telemetry`, la repartición la hace el broker.

### Telemetry receiver (gNMI/57400)

- Servicio TCP, escala como cualquier API
- Estado **opcional** (cache de sesiones) — si lo hay, va en Redis, no en memoria
- HPA por memoria recomendado (buffering de mensajes)

### SNMP Trap receiver (UDP/162)

UDP requiere consideraciones especiales:

- Opción A (recomendado): **DaemonSet** con `hostNetwork: true` o
  `hostPort: 162` — cada nodo escucha y publica al event bus.
- Opción B: Deployment con `externalTrafficPolicy: Local` + LB UDP (MetalLB,
  AWS NLB). Mayor latencia, pero más portable.
- Los traps NUNCA se procesan en el receiver — sólo se publican al bus y los
  worker-alarm hacen correlación.

### Postgres / TimescaleDB

**No usar el StatefulSet incluido en el chart en producción.** Es para dev/lab.

Opciones productivas:

| Opción                  | RTO   | RPO   | Notas                                       |
|-------------------------|-------|-------|---------------------------------------------|
| RDS / Aurora Postgres   | 60 s  | 5 s   | Más simple; usa `pglogical` para TimescaleDB|
| Patroni + etcd          | 30 s  | 0     | Autónomo, requiere etcd HA                  |
| Crunchy Postgres Op.    | 60 s  | 0     | K8s-native, replica sync en otra AZ         |
| Aiven / Timescale Cloud | 30 s  | 0     | TimescaleDB nativo, soporte 24/7            |

Apunta a la DB externa con:

```yaml
postgres:
  enabled: false
  externalHost: nms-pg.prod.svc:5432
secrets:
  existingSecret: nms-postgres-credentials   # password, sslrootcert
```

### Redis

Para HA usa **Redis Sentinel** o **Redis Cluster**:

- Sentinel (3+ sentinels): failover automático, sigue siendo single-primary.
  Suficiente para nuestra carga.
- Cluster (6+ nodos): sharding nativo. Sólo necesario en XLarge si Redis Streams
  se vuelve cuello de botella (>200k msg/s sostenido).

```yaml
redis:
  enabled: false
  externalHost: redis-master.prod.svc:6379
config:
  redisSentinelMaster: "nms-master"          # cuando aplica
```

---

## Event bus: Redis Streams vs Kafka

NMS_Custom soporta dos backends para el event bus. La elección depende de
escala, retención y madurez operacional del equipo.

### Comparativa

| Atributo                       | Redis Streams (default)            | Kafka (opcional)                 |
|--------------------------------|------------------------------------|----------------------------------|
| Throughput (1 nodo)            | ~500 k – 1 M msg/s                 | ~1 M+ msg/s                      |
| Latencia p99                   | <1 ms                              | 2–10 ms                          |
| Retención típica               | Horas/días (`MAXLEN ~ 10 k–1 M`)   | Días/semanas/meses               |
| Consumer groups                | ✅ nativo                          | ✅ nativo                        |
| Replay histórico               | Limitado (MAXLEN)                  | ✅ desde offset                  |
| Operación                      | Simple (Sentinel)                  | Compleja (Zookeeper/KRaft)       |
| Footprint mínimo               | 1 nodo (HA: 3 sentinels)           | 3 brokers + KRaft                |
| Federación cross-región        | Manual (MIGRATE / DUMP)            | MirrorMaker 2.0                  |
| Exactly-once                   | At-least-once + idempotencia       | EOS nativo (transactional)       |

### Cuándo usar Redis Streams (default)

- ≤ 5 000 dispositivos
- Retención de eventos ≤ 24 h
- Un solo cluster / región
- Equipo ya opera Redis para cache/queue
- Latencia p99 < 1 ms importa (alarmas en tiempo real)

### Cuándo usar Kafka

- > 5 000 dispositivos o > 500 k msg/s sostenido
- Retención de eventos > 7 días (compliance, auditoría, replay)
- Múltiples consumer groups con cargas muy distintas (analytics, ML, alarms)
- Federación multi-cluster con MirrorMaker 2.0
- Tu organización ya opera Kafka y tiene SRE para él

### Cambiar entre backends

El bus está abstraído tras `app.services.events.bus.EventBus`. Cambiar
backend = una variable de entorno:

```bash
EVENT_BUS_BACKEND=redis        # default
EVENT_BUS_BACKEND=kafka        # producción Kafka
KAFKA_BROKERS=kafka-0:9092,kafka-1:9092,kafka-2:9092
KAFKA_TOPIC_PREFIX=nms
```

En el chart:

```yaml
config:
  eventBusBackend: kafka
  kafkaBrokers: kafka.prod.svc:9092
  kafkaTopicPrefix: nms
kafka:
  enabled: true        # despliega el subchart bitnami/kafka (3 brokers)
```

> **Nota:** El backend Kafka comparte el mismo `EventEnvelope` y semántica
> consumer-group del backend Redis, así que los workers no cambian.

---

## Sharding de workers

Para el poller SNMP (el más caro en CPU/red), partimos por `device_id`:

```python
# Cada réplica recibe SHARD_ID y SHARD_COUNT vía env
if hash(device.id) % SHARD_COUNT == SHARD_ID:
    poll(device)
```

Configurado en el chart:

```yaml
config:
  workerShardCount: "4"          # debe coincidir con replicaCount.poller
replicaCount:
  poller: 4
```

**Reglas:**

- `workerShardCount == replicaCount.poller` (siempre)
- Reescalar **drena** primero (graceful shutdown) y luego reasigna shards en el rebalanceo
- HPA está deshabilitado para el poller — cambiar shard requiere coordinación

Para workers que consumen del bus (alarm, telemetry, fanout), **no se shardean
manualmente** — el consumer-group lo hace. HPA libre.

---

## Multi-cluster / multi-región

### Hub-and-spoke (recomendado para XLarge)

```
        ┌─────────────────────────────┐
        │   Hub cluster (us-east)     │
        │  ┌──────────┐  ┌─────────┐  │
        │  │ Postgres │  │ Reports │  │
        │  │ Central  │  │ Frontend│  │
        │  └─────▲────┘  └─────────┘  │
        └────────┼────────────────────┘
                 │ Kafka MirrorMaker / API push
   ┌─────────────┼─────────────┬─────────────┐
   │             │             │             │
┌──▼──┐      ┌──▼──┐       ┌──▼──┐       ┌──▼──┐
│Spoke│      │Spoke│       │Spoke│       │Spoke│
│ MX  │      │ EU  │       │ APAC│       │ EDGE│
│500dv│      │1500 │       │ 800 │       │ 200 │
└─────┘      └─────┘       └─────┘       └─────┘
```

Cada **spoke**:
- Cluster K8s independiente, ≥3 nodos
- NMS_Custom completo, DB local (TimescaleDB), Redis local
- Polling y trap reception locales (latencia baja a los devices)
- Publica eventos al hub vía Kafka MirrorMaker (preferido) o API REST push

El **hub**:
- Inventario global y vista federada (read-only desde la UI central)
- Reports cross-region
- Single sign-on, RBAC global
- Backup centralizado de configs (S3 multi-region)

### Federación de inventario

Cada spoke expone `/api/devices?federation=true` con un token de federación.
El hub agrega cada N minutos vía un worker `federation_pull`. Conflictos se
resuelven por `last_writer_wins` con timestamp del spoke.

### DNS y service discovery

- DNS global (Route53, Cloud DNS) con health checks por región
- Geo-routing para la UI: `nms.example.com` → cluster más cercano
- Trap receivers SIEMPRE locales — nunca atravesar región para SNMP UDP

### Disaster recovery cross-region

1. Postgres: réplica física (streaming) o lógica (pglogical) a otra región
2. Object storage de configs/reports: S3 cross-region replication
3. TLS certs: cert-manager con DNS-01 funciona en cualquier cluster
4. Failover manual: actualizar DNS + promover replica. RTO objetivo: 15 min.

---

## Capacity planning

### Fórmulas base

**Polling load:**

```
ops_por_segundo = (devices × oids_por_device) / poll_interval_seconds
```

Ejemplo: 2 000 devices × 50 OIDs / 60 s = **~1 700 SNMP ops/s**

**CPU por worker poller (asyncio):** ~500 ops/s sostenido por core.
→ 2 000 devices = 4 cores total = **2 réplicas × 2 cores**.

**KPI writes a TimescaleDB:**

```
inserts_por_segundo = devices × kpis_por_device / poll_interval
```

Con compresión TimescaleDB y `INSERT ... ON CONFLICT` batch de 1 000 →
hasta **20 k inserts/s en una instancia 4-core / 16 GiB**.

**Retención de KPIs (TimescaleDB):**

| Granularidad | Retención | Continuous aggregate |
|--------------|-----------|----------------------|
| Raw (1 min)  | 7 días    | n/a                  |
| 5-min rollup | 30 días   | `cagg_5m`            |
| 1-h rollup   | 1 año     | `cagg_1h`            |
| 1-d rollup   | 5 años    | `cagg_1d`            |

### Dimensionamiento por talla

| Talla   | API CPU | API RAM | Worker CPU total | DB CPU | DB RAM | DB Disco | Redis RAM |
|---------|--------:|--------:|-----------------:|-------:|-------:|---------:|----------:|
| Small   |   2 c   |   2 Gi  |              4 c |    2 c |   8 Gi |   100 Gi |     2 Gi  |
| Medium  |   4 c   |   4 Gi  |              8 c |    4 c |  16 Gi |   500 Gi |     4 Gi  |
| Large   |   8 c   |   8 Gi  |             16 c |    8 c |  32 Gi |     2 Ti |     8 Gi  |
| XLarge  |  16 c   |  16 Gi  |             32 c |   16 c |  64 Gi |     5 Ti |    16 Gi  |

---

## Tuning y benchmarks

### Backend

- `WORKER_MAX_CONCURRENCY=8` por defecto → subir a 16 en pollers con red rápida
- `POSTGRES_POOL_SIZE=20` por réplica API; cuidar `max_connections` global de la DB
- `EVENT_CONSUMER_BLOCK_MS=1000` → bajar a 100 ms si latencia de alarma importa
- `TELEMETRY_BUFFER_FLUSH_MS=500` → balance entre throughput y latencia

### TimescaleDB

```sql
-- Hypertable con chunk de 1 día (default 7 días es muy grande para nuestro patrón)
SELECT set_chunk_time_interval('kpis', INTERVAL '1 day');

-- Compresión a partir del día 7
ALTER TABLE kpis SET (timescaledb.compress, timescaledb.compress_segmentby = 'device_id');
SELECT add_compression_policy('kpis', INTERVAL '7 days');

-- Retención automática
SELECT add_retention_policy('kpis', INTERVAL '30 days');
```

### Redis Streams

- `MAXLEN ~ 100000` para `nms:events` (≈ 50 MiB por stream)
- `min-idle-ms = 60000` para `XAUTOCLAIM` (1 min de gracia antes de reclamar)
- `XPENDING` monitoreado vía Prometheus — alerta si > 1 000 mensajes pendientes

### Network

- MTU 9000 en la red intra-cluster si el NIC lo soporta (jumbo frames)
- SNMP poller en pods con `dnsPolicy: ClusterFirstWithHostNet` si los devices están en la host network

---

## Failure modes y recuperación

| Failure                              | Detección                          | Mitigación                                     |
|--------------------------------------|------------------------------------|------------------------------------------------|
| Pod API crashloop                    | Readiness probe falla              | HPA mantiene minReplicas, k8s reinicia         |
| Postgres primary down                | Probe TCP + readiness API          | Failover Patroni/RDS (60 s); API en 503 hasta  |
| Redis primary down                   | Sentinel detecta, promueve replica | Workers reconectan; events en buffer local 30s |
| Stream backlog crece                 | Métrica `xpending_count`           | Escalar worker; investigar lentitud DB         |
| Stale consumer (worker congelado)    | `XAUTOCLAIM` cada 60 s             | Otro worker reclama el lease automáticamente   |
| Discovery worker duplicado           | Lease en Redis (`SET NX EX 300`)   | Sólo el dueño del lease ejecuta el ciclo       |
| Zona AZ entera down                  | NodeNotReady en 1 AZ               | `topologySpreadConstraints` mantiene 2/3 vivas |
| Trap UDP perdido                     | Counter `traps_received` plano     | DaemonSet en cada nodo; alerta de tasa anormal |
| Certificados TLS expirados           | cert-manager prometheus alert      | Renovación automática; alerta 14 días antes    |
| Bloat de WAL en Postgres             | Métrica `pg_wal_size_bytes`        | Aumentar `max_wal_size`; replica de archivado  |

### Runbook de incidente (resumen)

1. **Triaje** — ¿API caída total o degradada? Mirar `/healthz` por réplica.
2. **DB** — `pg_isready`, replication lag, `pg_stat_activity` por queries lentas.
3. **Redis** — `INFO replication`, `XLEN` por stream, `XPENDING` por grupo.
4. **Workers** — `xpending_count` por consumer, logs estructurados con `trace_id`.
5. **Devices** — ¿spike de polling fallido? Filtrar por `device.region`.
6. **Roll-back** — `helm rollback nms-custom` a la revisión anterior si fue un despliegue malo.

---

## Referencias internas

- [ARCHITECTURE.md](./ARCHITECTURE.md) — diseño general
- [NMS_ARCHITECTURE_EXECUTION_PLAN.md](./NMS_ARCHITECTURE_EXECUTION_PLAN.md) — roadmap por fases
- `helm/nms-custom/values-prod.yaml` — defaults productivos
- `helm/nms-custom/values-ha.yaml` — overrides HA multi-AZ
