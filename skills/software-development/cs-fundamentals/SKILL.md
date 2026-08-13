---
name: cs-fundamentals
description: Compact reference of computer science fundamentals — data structures, algorithms & complexity, OS concepts, networking, databases, concurrency, and systems design. Use to ground engineering decisions in CS basics, refresh a concept, or explain a trade-off with first principles.
---

# CS Fundamentals Reference

Grounds engineering work in first principles. Not a textbook — a refresher for
decisions and trade-offs. Go deeper via the pointers at the end.

## Complexity (Big-O)

- Time: O(1) < O(log n) < O(n) < O(n log n) < O(n²) < O(2ⁿ)
- Space is a cost too — always state it alongside time.
- Rule of thumb: n ≈ 10⁶ operations/sec for interpreted code, 10⁸-10⁹ for
  compiled. Amortized (hash tables, dynamic arrays) beats worst-case in practice.

## Data structures — when to reach for each

| Structure | Strengths | Watch out for |
|---|---|---|
| Array/Vector | cache-friendly, random access | insertion/deletion at head |
| Linked list | cheap head/tail ops | pointer chasing, cache misses |
| Hash map | O(1) avg lookup | poor locality, collision attacks |
| Tree (BST/AVL/B-tree) | ordered ops, range scans | balancing cost; B-tree for disk |
| Heap | priority queues, top-K | no search |
| Trie | prefix search, autocomplete | memory |
| Graph (adj list/matrix) | relationships, paths | scale (see traversal) |
| Bloom filter / LSM | membership approx / write-heavy DB | false positives / compaction |

## Algorithms worth naming

- Sorting: stable vs unstable; Timsort (Python/JS default) is hybrid
- Search: binary search on sorted data; BFS for shortest hops, DFS for
  reachability/topology; Dijkstra (non-negative weights), A* (heuristic)
- Two pointers, sliding window, divide & conquer, backtracking
- Hashing: consistent hashing (sharding), Merkle trees (integrity/replication)
- MapReduce-style: split → map → shuffle → reduce

## OS

- Process vs thread vs coroutine: isolation vs sharing vs lightweight
- Syscalls are the boundary; context switches are expensive (~µs)
- Virtual memory: pages, TLB, mmap, copy-on-write forks
- Filesystems: inodes, ext4/xfs/ZFS/btrfs trade-offs, fsync semantics
- Scheduler: CFS/EEVDF, I/O vs CPU bound, nice/ionice
- Signals, file descriptors (ulimit), OOM killer — failure modes to know

## Concurrency

- Races, deadlock (4 conditions; break one), livelock, starvation
- Locks, atomics, RW-locks, condition variables, semaphores; lock-free = hard
- Actor model, channels (Go), async/await: which model the stack uses matters
- Transactional guarantees: check-and-set, compare-and-swap, idempotency

## Networking

- OSI vs TCP/IP; the layers you debug: L1-L4 vs L7
- TCP: 3-way handshake, congestion control, TIME_WAIT; UDP for loss-tolerant
- DNS resolution order, TTLs; HTTP: methods, status codes, caching, keep-alive,
  HTTP/2 multiplexing, HTTP/3 QUIC
- TLS: handshake, cert chains, SNI, ALPN; mTLS for service-to-service
- Load balancing: L4 vs L7, sticky sessions, health checks

## Databases

- ACID vs BASE; isolation levels (read committed vs serializable)
- Indexes: B-tree (range), hash (point), covering indexes; EXPLAIN plans
- Normalization vs denormalization; read/write amplification
- SQL vs NoSQL trade-offs: document (flexible schema), wide-column,
  key-value, graph, time-series
- Replication (leader/follower), partitioning/sharding, consistency models
  (strong vs eventual, quorum)

## Systems design basics

- Scale levers, in order: cache → async/queue → partition → replicate → CDN
- Cache: read-through/write-through, TTL, invalidation, cache stampede
- Queues: backpressure, retries with backoff + jitter, DLQ, at-least-once vs
  exactly-once (idempotent consumers)
- CAP: consistency vs availability under partition; choose deliberately
- Observability: metrics/logs/traces (see observability skill); SLOs
- Backups: 3-2-1 rule, tested restores (see backup skill)

## Engineering hygiene (first principles)

- Clean naming: name things by what they do/mean, not how implemented
- Keep history: commits explain "why", docs capture decisions (see
  keep-the-why), ADRs for architecture (see architecture-decision-record-drafter)
- Simplicity: least moving parts; complexity is a tax, not a feature

## Where to go deeper

- Algorithms: CLRS / "Competitive Programming" books; leetcode patterns
- OS: "Operating Systems: Three Easy Pieces" (free, ostep.org)
- Networking: Kurose & Ross; "Computer Networking: Principles, Protocols and
  Practice" (free)
- DB: "Designing Data-Intensive Applications" (Kleppmann)
- Systems: DDIA again; "System Design Interview" pattern books
