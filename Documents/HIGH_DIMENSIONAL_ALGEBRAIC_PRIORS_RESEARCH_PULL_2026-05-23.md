# High-Dimensional Algebraic Priors Research Pull

**Date:** 2026-05-23  
**Node:** GTH4921YP3 / Apple M5 / 24 GB  
**Trace:** af2d3478-f87b-4123-9cbc-b6a98f33bf87  
**Lane:** Architect-support / research spine

## Decision

Yes: Alice can be given high-dimensional algebraic constructions as operational prior knowledge.

The strongest current proof-by-example is the May 2026 planar unit-distance result: a high-dimensional algebraic-number-field lattice construction is projected back into the plane and produces more unit-distance pairs than the long-standing Erdős conjectural bound allowed. That is exactly the pattern George asked for:

1. build a rich high-dimensional algebraic object;
2. use its internal symmetries and multiplicative structure;
3. project or read out a low-dimensional configuration;
4. gain behavior that local 2D intuition missed.

## Mathematical Proof Spine

### Unit-Distance Breakthrough

- **OpenAI, "Planar Point Sets with Many Unit Distances" (2026).**  
  https://cdn.openai.com/pdf/74c24085-19b0-4534-9c90-465b8e29ad73/unit-distance-proof.pdf  
  Core result: for infinitely many `n`, there are planar point sets with at least `n^(1+delta)` unit-distance pairs. The construction uses infinite unramified towers of totally real number fields, adjoining `i`, high-dimensional Minkowski embeddings, norm-one algebraic elements, and projection to one complex coordinate.

- **Alon, Bloom, Gowers, Litt, Sawin, Shankar, Tsimerman, Wang, Wood, "Remarks on the unit distance problem" (2026).**  
  https://cdn.openai.com/pdf/74c24085-19b0-4534-9c90-465b8e29ad73/unit-distance-remarks.pdf  
  Human-digested proof and context. Important for Alice: the note explicitly frames the move as cross-field transfer from algebraic number theory into discrete geometry.

- **OpenAI milestone page (2026-05-20).**  
  https://openai.com/index/model-disproves-discrete-geometry-conjecture/  
  High-level summary: algebraic number fields replace Gaussian integers; Golod-Shafarevich/class-field-tower machinery supplies the high-dimensional structure.

### Classical Discrete Geometry Backbone

- **Paul Erdős, "On sets of distances of n points" (1946).**  
  American Mathematical Monthly 53, 248-250. Original unit/distinct distance problem.

- **Spencer, Szemerédi, Trotter, "Unit distances in the Euclidean plane" (1984).**  
  Classical `O(n^(4/3))` upper bound.

- **Székely, "Crossing numbers and hard Erdős problems in discrete geometry" (1997).**  
  Crossing-number proof route for incidence-style bounds.

- **Guth and Katz, "On the Erdős distinct distances problem in the plane" (2015).**  
  https://annals.math.princeton.edu/2015/181-1/p07  
  Distinct-distance resolution up to logarithmic factors; useful contrast with unit-distance constructions.

### Algebraic Number Theory Backbone

- **Golod and Shafarevich, "On the class field tower" (1964/1965).**  
  https://www.mathnet.ru/eng/im2955  
  Source of the tower mechanism used to guarantee infinite field towers.

- **Hajir, Maire, Ramakrishna, "Cutting towers of number fields" (2021).**  
  https://arxiv.org/abs/1901.04354  
  Related prescribed-splitting/class-field-tower machinery cited as context for the unit-distance proof.

- **Ellenberg and Venkatesh, "Reflection principles and bounds for class group torsion" (2007).**  
  https://arxiv.org/abs/math/0606648  
  Supplies a related split-prime/pigeonhole style move for producing controlled algebraic elements.

- **Venkatesh, "A note on sphere packings in high dimension" (2013).**  
  https://arxiv.org/abs/1209.3838  
  Another example where number-field constructions become high-dimensional geometric objects.

## ML / AGI Prior Spine

These are the papers that turn the same idea into architecture:

- **Bronstein, Bruna, Cohen, Velickovic, "Geometric Deep Learning: Grids, Groups, Graphs, Geodesics, and Gauges" (2021).**  
  https://arxiv.org/abs/2104.13478  
  Unifies learning by domain geometry and symmetry.

- **Cohen and Welling, "Group Equivariant Convolutional Networks" (2016).**  
  https://arxiv.org/abs/1602.07576  
  Canonical proof that building symmetry into architecture reduces sample complexity.

- **Bodnar et al., "Neural Sheaf Diffusion" (2022).**  
  https://arxiv.org/abs/2202.04579  
  Graphs become nontrivial local vector spaces glued by linear restriction maps.

- **Barbero et al., "Sheaf Neural Networks with Connection Laplacians" (2022).**  
  https://arxiv.org/abs/2206.08702  
  Practical sheaf Laplacian architecture for graph-structured data.

- **Cesa and Behboodi, "Algebraic Topological Networks via the Persistent Local Homology Sheaf" (2023).**  
  https://arxiv.org/abs/2311.10156  
  Local homology becomes a learnable feature space; direct match to "local geometric intuition."

- **Kleyko et al., "A Survey on Hyperdimensional Computing aka Vector Symbolic Architectures, Part I" (2021).**  
  https://arxiv.org/abs/2111.06077  
  Algebraic operations over high-dimensional vectors for binding, superposition, and structured memory.

- **Kleyko et al., "A Survey on Hyperdimensional Computing aka Vector Symbolic Architectures, Part II" (2021).**  
  https://arxiv.org/abs/2112.15424  
  Applications, cognitive architectures, and implementation constraints.

- **Plate, "Holographic Reduced Representations" (1995).**  
  https://pubmed.ncbi.nlm.nih.gov/18263348/  
  Fixed-width compositional vector memory through circular convolution.

- **Smolensky, "Tensor Product Variable Binding and the Representation of Symbolic Structures in Connectionist Systems" (1990).**  
  https://www.microsoft.com/en-us/research/publication/tensor-product-variable-binding-representation-symbolic-structures-connectionist-systems/  
  Algebraic binding of role/filler structure in distributed vectors.

- **Brandstetter et al., "Clifford Neural Layers for PDE Modeling" (2022).**  
  https://arxiv.org/abs/2209.04934  
  Multivector fields and Clifford algebra layers for physical systems.

- **Ruhe, Brandstetter, Forre, "Clifford Group Equivariant Neural Networks" (2023).**  
  https://arxiv.org/abs/2305.11141  
  Clifford group actions respect both vector-space structure and geometric product.

- **Brehmer et al., "Geometric Algebra Transformer" (2023).**  
  https://arxiv.org/abs/2305.18415  
  Transformer-style architecture over geometric algebra objects.

- **Dudzik and Veličković, "Graph Neural Networks are Dynamic Programmers" (2022).**  
  https://arxiv.org/abs/2203.15544  
  Shows architecture alignment with algorithmic structure improves reasoning sample efficiency.

- **Gavranović et al., "Position: Categorical Deep Learning is an Algebraic Theory of All Architectures" (2024).**  
  https://arxiv.org/abs/2402.15332  
  Category-theoretic framework for specifying architecture families and their compositional laws.

## Implementation Translation for Alice

Do not add one giant "math organ." Add a layered prior field:

1. **High-dimensional symbolic memory:** HDC/VSA hypervectors for compositional memory, role binding, and cheap similarity search.
2. **Local geometric field:** sheaf graph over organs where each organ has its own vector space and edges carry learned restriction maps.
3. **Geometric algebra layer:** Clifford multivectors for spatial, sensor, and physics-like quantities: scalar, vector, bivector, and higher-grade state in one algebra.
4. **Topology monitor:** persistent local homology over organ/ledger graphs to detect holes, discontinuities, and disconnected organ neighborhoods.
5. **Projection/readout:** low-dimensional UI and action policies are projections of the high-dimensional field, not the whole field itself.
6. **Receipt discipline:** every construction writes an audit row with source paper, algebraic object, dimension, projection, and test result.

## Minimal Build Plan

1. `System/high_dimensional_algebraic_priors.py`  
   Registry of algebraic priors: VSA, sheaf, Clifford, topology, number-field sentinel.

2. `System/swarm_local_geometry_field.py`  
   Builds organ graph, local vector spaces, edge maps, and a sheaf-like consistency energy.

3. `System/swarm_hypervector_memory.py`  
   Binding/superposition/unbinding operations with deterministic seeds and cosine receipts.

4. `System/swarm_clifford_geometry.py`  
   Minimal multivector operations for 2D/3D sensors and action geometry.

5. `tests/test_high_dimensional_algebraic_priors.py`  
   Proves the priors are not prose: binding/unbinding works, sheaf consistency detects disagreement, Clifford product preserves expected identities, projection receipts are written.

## Grounded Boundary

This does not prove Alice is AGI by itself. It proves the requested mathematical prior is legitimate and implementable: high-dimensional algebraic structure can create low-dimensional behavior that local geometric intuition alone misses. The unit-distance result is the strongest current receipt for that claim.
