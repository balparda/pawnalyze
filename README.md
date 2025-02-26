# pawnalyze

Parse and analyze historical chess games: frequencies, trends, player styles, etc.

## Overview

This project aims to analyze chess game trends over time by parsing, structuring, and analyzing large publicly available PGN datasets. The focus is on move frequencies, historical trends, and player styles rather than machine learning.

The project aims to push beyond simple database queries by building an integrated system where we can traverse and query the entire space of chess games in memory (or with seamless disk support). By having both the position-based and move-sequence–based indexes, we enable rich queries that typical chess databases or PGN readers don’t easily support. The combination of historical data and these structures allows for innovative analysis – from plotting the rise and fall of opening lines, to quantifying stylistic shifts in play. This comprehensive approach will yield insights into how chess strategy and preferences have evolved, backed by hard data and efficient algorithms to crunch it. The plan above ensures we can handle the volume of data and extract meaningful patterns to advance chess research in novel ways.

## Available Data Sources

Finding a large, free chess game dataset is crucial for broad trend analysis. Below are notable publicly available PGN databases containing millions of games spanning different historical eras:
- **LumbrasGigaBase (2025)** – A massive collection of about 15 million chess games aggregated from various sources (The Week in Chess, PGN Mentor, MillionBase, etc.), covering historical classics up to modern games ￼ ￼. It is available for free download in PGN format and includes tags denoting source archives (e.g., Britbase for 19th-century British games) to ensure broad era coverage.
- **MillionBase & Caissabase** – Community-curated databases of high-quality games. MillionBase 2017 contains ~2.9 million master-level games spanning 1800s through 2017 ￼ ￼. It has been incorporated into larger sets like Caissabase (≈4.3 million games) and LumbrasGigaBase. These include games from early recorded history (e.g., 1780s) up to recent times, enabling century-long trend analysis.
- **KingBase 2019** – A free database of about 2.2 million games from 1990–2019, filtered for strong players (ELO >2000) ￼. While focused on late-20th and 21st-century master games, it provides depth in modern-era play and can complement historical datasets.
- **Figshare Historical Chess Database** – An open dataset of 3.5 million games in PGN covering 1783 to 2009, compiled for research ￼. This dataset explicitly includes centuries of games (from Gioachino Greco’s era through the modern age), ideal for long-term move trend analysis.
- **Online Play Databases** (Supplementary) – For sheer volume, platforms like Lichess offer billions of crowd-sourced games (monthly dumps on <database.lichess.org>), and FICS/ICC archives contain millions. These are mostly post-2000 internet games, so while great for volume and modern patterns, they require filtering for quality and don’t span the pre-digital era. They can be used alongside historical PGNs for contrast.

Each of these datasets is free and suitable for research. Combining them yields a comprehensive collection of games from the Romantic era of the 19th century (when daring gambits like the King’s Gambit were common ￼) through the hypermodern and computer-influenced play of the 21st century. This breadth will support robust trend analysis across eras.

Using the above data, we can design an innovative chess research project focusing on move frequencies, historical trends, and player styles. The project will involve efficient data parsing, robust in-memory structures for analysis, and methods to extract insights. Below is a detailed plan covering each aspect.

## Implementation Plan

### 1. PGN Parsing Strategy

Efficient Extraction of Moves, Positions, and Metadata: Parsing millions of games requires a careful strategy to avoid memory blow-ups and slow processing. We will use streaming PGN parsing to read one game at a time, extracting moves and metadata without loading the entire file into memory. In Python, a reliable approach is to use the chess.pgn module from the python-chess library, which can iterate through PGN files game by game. For each game:
- **Moves and Board States**: Parse the move text into a structured format. With python-chess, we can obtain a Board object and apply moves sequentially. After each move, record the move notation (e.g., e4) and compute a hash of the resulting board position (using a Zobrist hashing method for compactness, discussed below). This yields the sequence of (move, position_hash) pairs for the game.
- **Game Metadata**: Extract tags like Year/Date, Players, Event, and ECO code. The year or precise date lets us slot the game into a historical timeline (to analyze era trends), and ECO codes or opening names give a classification of the opening used.
- **Handling PGN Structure**: PGN files often contain commentary, annotations, or variations. Our parser will ignore bracketed comments and skip alternate lines (unless analysis of those is desired) to focus only on the main line moves. Using a well-tested library helps ensure we handle standard PGN format edge cases (like resumptions, promotion notation, etc.). If performance becomes an issue, a possibility is writing a custom parser that uses simpler string tokenization for moves, but leveraging an existing library is safer initially.
- **Iterative/Parallel Processing**: To speed up parsing of very large datasets, we can split the input. Many PGN collections are provided as multiple files (e.g., by year or source). We can run parsing in parallel threads or processes for different files (taking care to aggregate results thread-safely). If we have one gigantic PGN file, we could preprocess it to split on game boundaries (PGN games are separated by blank lines and the [Event tag) and distribute chunks to workers. This parallel approach has been used in large-scale chess data processing ￼ ￼, drastically reducing ingestion time.

Outcome: The parser will output a stream of game data: for each game, a list of moves with corresponding position hashes, along with metadata (date, players, result, etc.). This feeds into building our data structures.

### 2. Data Structures

To facilitate efficient queries on moves and positions, we’ll build two complementary in-memory dictionaries:

#### POSITIONS Dictionary (Move Graph)

This is essentially a graph representation of chess positions and transitions. Each unique board position (identified by a hash) is a key. The value is a list of possible moves from that position and the resulting positions. For example, POSITIONS[pos_hash] = [(move1, next_pos_hash1), (move2, next_pos_hash2), ...]. This means from position pos_hash, move move1 leads to position next_pos_hash1, etc. In practice, we might use a tuple or small dict instead of list to also store metadata like move frequency. This structure acts like an opening book or state transition map – given any position, one can quickly look up all moves that were played from it in the dataset. It’s essentially an adjacency list for the game graph.

- Stores legal moves from each position.
- Fast O(1) lookup for all moves from a given position.

```python
POSITIONS = {
    position_hash: [(move, next_position_hash, frequency), ...]
}
```

#### GAMES Dictionary (Nested Trie)
This is a tree (trie) of move sequences mapping out every game in the dataset. The idea is to nest dictionaries to represent successive plies. The top-level keys are the first moves of games ('e4', 'd4', 'Nf3', etc.), each pointing to a dictionary of second moves, and so on. To also quickly retrieve the resulting position at each step, we store the position hash alongside the nested dict. For example, one entry might look like:

- Stores move sequences compactly by merging common prefixes.
- Allows querying for move sequence frequency and trends.

```python
GAMES = {
    'e4': (hash_after_e4, {
        'e5': (hash_after_e4_e5, {
            'Nf3': (hash_after_e4_e5_Nf3, { ... })
        })
    }),
    'd4': (hash_after_d4, { ... })
}
```

Here GAMES['e4'][0] is the hash after White plays e4, and GAMES['e4'][1] is the dictionary of Black’s replies. This nesting continues until the end of a game, where we can store a terminal marker or a reference (like a game ID or index to the PGN) indicating the game’s conclusion. For instance, the last move might map to ('final_position_hash', None) or contain a pointer to the game record for lookup. This structure compactly merges common prefixes of games: all games starting with 1.e4 e5 share the same initial branch in the tree. This not only saves space through compression of shared openings, but also enables quick traversal of all moves of any game or opening line. It’s similar to how opening books and some databases store moves in a tree ￼. We can also augment each node with counters (e.g., how many games went through that node) to get frequency data on the fly.

Relationship between POSITIONS and GAMES: These two structures provide two lenses on the data. The GAMES trie is excellent for reconstructing full games or common sequences (e.g. to find all games that followed a particular opening line). The POSITIONS dict is optimized for queries by position, regardless of how one reached there (useful for finding all continuations from a given board configuration, even if it arises via different move orders). They can be built simultaneously during parsing: as we step through moves in a game, update the GAMES nested dict and also update POSITIONS for each position transition.

Example Use: If we want to analyze the moves from the standard opening position, we look at POSITIONS[initial_hash] and see moves like e4, d4, Nf3, c4... with their frequencies. If we want the popularity of a specific sequence, like the Sicilian Defense (1.e4 c5 2.Nf3 d6), we traverse GAMES['e4'][1]['c5'][1]['Nf3'][1]['d6'] to reach that node, and we could retrieve how many games followed it and what White played next from POSITIONS[hash_after_e4_c5_Nf3_d6].

This design emphasizes fast in-memory lookups and structural sharing. By using position hashes as keys (instead of storing full FEN strings or board arrays), we keep keys compact. The use of nested dictionaries for GAMES naturally compresses repeated sequences (common openings stored once), which is memory-efficient given redundancy in chess games.

### 3. Efficient Data Handling

Dealing with millions of games means handling potentially billions of positions and moves. We need strategies for compact storage and fast access:

- **Compact Position Keys (Hashing)**: We will use Zobrist hashing to represent each board position as a 64-bit integer. A Zobrist hash is essentially an almost-unique fingerprint for a chess position ￼. It’s generated by XORing random bitstrings for each piece on each square (and the side to move, castling rights, etc.). This yields a fixed-size key (8 bytes) per position instead of storing a full board matrix or FEN string. Zobrist hashes are designed to minimize collisions (the chance that two distinct positions share a hash is astronomically low). Using a 64-bit integer key is extremely memory efficient and quick to compare, enabling the POSITIONS dictionary to use hashes as keys for O(1) lookups in memory. (In practice, Python’s hash() on a board state isn’t reliable across runs, so we’ll implement Zobrist or use the one in python-chess to get a stable key.) This hashing approach is widely used in chess engines for transposition tables and databases to index positions ￼.
- **Memory Efficiency and Compression**: Even with compact keys, storing billions of entries naively will exhaust memory. We must be judicious and possibly compress or limit data:
- **Structural Compression**: The nested GAMES trie already avoids storing duplicate sequences multiple times. For positions, many positions occur in multiple games, but we store each unique position once. We can further compress by not storing transient or rarely-used positions. For example, we might choose to store only positions up to a certain ply depth in memory if deep endgame positions aren’t needed for our analysis, or store only positions that occur in at least 2 games, etc., to trim extremely unique branches.
- **Data Packing**: The values in POSITIONS (move and next_hash pairs) can be stored as tuples of integers or even a single binary-packed structure (e.g., combine move encoding and hash). Since a move can be encoded in a couple of bytes (there are only 64 source and 64 destination squares, plus promotion info), one idea is to encode a move as, say, 16 bits, and store it alongside the 64-bit next hash in a 10-byte record. Storing such records in a Python list still has overhead, but using array libraries or memoryviews could be a more efficient representation than a list of Python objects.
- **Lazy Loading**: Another technique is not to build the entire structure upfront. Instead, we could generate data on the fly for certain queries. For instance, we might not need all positions in memory at once – we could stream through games to calculate frequency statistics, aggregating counts without storing every detail permanently. On-demand computation or storing only aggregated counts rather than full lists could save space.
- **Compression Libraries**: If memory becomes a true bottleneck, we might consider compressing structures. For example, storing the GAMES tree in a compressed trie structure (there are Python libraries for compressed tries or we can serialize and compress). However, this might complicate retrieval logic. Another innovative idea is to use a disk-backed key-value store or memory-mapped file for the positions (see Scalability below), effectively compressing by using external storage.
- **Efficient Retrieval**: With the structures in place, retrieval of information should be optimized:
- **Looking up** all moves from a position is a direct dictionary access in POSITIONS by hash (average O(1) time). If we need to find a specific move from that position, we can scan the small list of moves or use a secondary dict for moves. Given that a chess position has at most 218 legal moves in extreme cases (usually much fewer), a short list is fine. If needed, we can sort the moves list and binary search, or simply use a dict mapping move->next_hash for constant lookups.
- **Finding a sequence** in GAMES is as fast as following the chain of dictionaries. Each move lookup is O(1) on average, so a sequence of k moves is O(k). This is efficient even for long games (k ~ 80 half-moves). We should ensure the dictionaries use Python’s built-in hash (which is very fast for short strings like move notation).
- **For frequency queries** (e.g., how often is a move played from a position), we could maintain counts during parsing. For example, each entry in the POSITIONS list could be a triple (move, next_hash, count) to record how many times that move occurred. Alternatively, each node in GAMES could have a counter of how many games went through it. Storing such counters adds memory overhead but makes retrieval of statistics direct. A compromise is to calculate frequencies post-hoc by iterating through games or positions and counting as needed, but that can be slow on demand. Given our research focus, it’s likely worth storing counts upfront for moves to allow instant queries like “How many times was 1.e4 played in the dataset?” or “Out of all games reaching this position, what percentage continued with move X?”.

In summary, by using 64-bit position hashes, sharing common sequences, and possibly augmenting with counts, we manage the data volume in memory. The key is that our approach treats the entire dataset as a big directed graph of positions, which can be traversed and queried efficiently. This is akin to an engine’s opening book or transposition table, repurposed for large-scale human game data – an approach that is powerful but not commonly implemented in off-the-shelf chess databases.

### 4. Trend Analysis

With the data parsed and organized, we can perform various analyses to uncover trends in move choices and player styles over time. Our analysis will not just re-confirm known trends (like “White wins slightly more often than Black” or “1.e4 is historically the most common opening move” ￼) but also attempt unique queries that haven’t been widely explored. For example, we might analyze center control over time (do modern players occupy the center with pawns more or less than classical players?), or the evolution of endgame technique (are certain drawn endgames more common now, indicating better defensive play?). By leveraging the rich data in our POSITIONS and GAMES structures, we can ask complex questions (like “what is the most common position that was a decisive turning point in a world championship match?”) and get answers by traversing or searching our data.

Here are the planned focus areas and some innovative angles for each:

#### Move Frequency Statistics

- Rank moves by frequency at each position.
- Identify rare moves or forgotten gambits.

Using the POSITIONS dictionary, we can easily compute how often each move is played from a given position. Starting with the initial position, we’ll calculate the popularity of first moves (e.g., what percentage of games start with 1.e4 vs 1.d4, etc.). Similarly, for any common position (say after 1.e4 e5), we can rank the moves by frequency (e.g., 2.Nf3 is played X% of the time, 2.Nc3 Y%, etc.). This can extend to full openings: by traversing the GAMES tree down a known sequence, we know how many games follow that line and where deviations occur. We plan to generate frequency tables for major openings and critical junctions in opening theory. This will highlight, for example, that 1.e4 dominates 1.d4 historically ￼ or that among 1.e4 e5 openings, 2.Nf3 vastly outweighs other second moves ￼. We can also identify rare moves or bygone practices (like unusual gambits) by finding moves with very low frequency overall or ones that were common only in a certain era.

#### Popular Openings Over Time

- Track opening popularity by decade.
- Detect when certain openings first appeared or disappeared.

By leveraging game dates, we will analyze how opening choices have evolved by era. We can group the games by decade (or specific periods like pre-1900, 1900-1950, 1950-2000, etc.) and compute the frequency of key openings in each period. This requires filtering the GAMES or game list by year and then counting sequences or ECO codes. For example, we expect to see the King’s Gambit (1.e4 e5 2.f4) was highly popular in the 19th century but nearly vanished by the mid-20th ￼, whereas defenses like the Sicilian (1.e4 c5) rose significantly post-World War II. We can verify these by plotting the percentage of games that feature a given opening over time. Another trend could be the shift from e4 to d4 as a preferred first move among top players in different eras. The data might reveal spikes in popularity corresponding to influential players or published analyses (e.g., the rise of the Najdorf Sicilian in the 1950s-60s, or the increased use of the Grünfeld Defense after the 1920s). We will also look at the diversity of openings: older eras might have a narrower set of popular openings (due to limited theory), whereas modern databases might show a wider variety of viable openings being tried.

#### Evolution of Player Styles

To analyze player style, we’ll combine quantitative metrics and perhaps more creative indicators:

- **Aggressiveness vs. Positional Play**: We can define metrics such as average piece mobility (how often do players move pieces into the opponent’s side of the board early), or count sacrificial moves (moves that intentionally give up material). For instance, the Romantic era (19th century) is known for aggressive play with gambits and sacrifices ￼, whereas later eras valued positional maneuvering. We can attempt to capture this by checking how frequently players in different eras gambited a pawn or made an early sacrifice. Another proxy is the prevalence of tactical motifs vs. quiet moves: e.g., how often is a check or capture played in the first 10 moves of games in 1880 vs 1980 vs 2020.
- **Opening vs Endgame Preference**: Some players steer games towards complex middlegames, others simplify to endgames. We could measure the average game length and how that changed – a shorter decisive game might indicate sharp tactical fights, whereas longer games suggest more endgame play. We expect to see that the draw rate and game length increased in modern elite play (players are more evenly matched and willing to play longer endgames), versus older eras with more decisive results in fewer moves.
- **Piece Usage Patterns**: We can track how often certain pieces are moved or exchanged. For example, a “dynamic attacker” might move knights and bishops more in early game, whereas a positional player might make more pawn moves to control space. By aggregating moves from many games of a single player or era, we can see patterns (e.g., do 19th-century games have more pawn storms and queen sorties than modern games?). We could select a few representative grandmasters from different eras (Morphy, Capablanca, Tal, Karpov, Carlsen) and compare statistics like percentage of games featuring gambits, average pawns moved in first 10 moves, frequency of opposite-side castling, etc., to quantitatively reflect style differences.
- **Clustering and Novel Metrics**: An innovative approach is to treat each player as a vector of features (opening preferences, move tendencies, common patterns) and perform clustering or dimensionality reduction. This could reveal groups of players with similar styles (regardless of era) and then we examine how those clusters correlate with time. Possibly, older clusters might all emphasize tactics while newer ones emphasize prophylaxis. This isn’t widely done in traditional chess analysis and could yield novel insights into the taxonomy of chess styles.

#### Historical Insights and Case Studies

Using the data, we will also drill down into specific historical questions as examples of trend analysis:

- **Identify when certain moves first appeared** in master play. For example, find the earliest game in the database with a specific novelty move, and see how it proliferated afterward. We could search the GAMES structure for a particular sequence and note its date tags to find the first occurrence.
- **Examine the impact of influential players** on move trends. For instance, if we look at the rise of the King’s Indian Defense in mid-20th century, how much was it driven by players like Bronstein or Fischer? We can filter games by player and see their opening repertoire frequencies, then see if overall frequencies followed their successes.
- **Win-rate analysis**: We can incorporate results (from PGN tags) to analyze which openings yield higher success for White or Black over time. For example, did the King’s Gambit actually give worse results for White, leading to its decline? We have the data to compute win/draw/loss percentages for each opening line, and see if those changed historically (perhaps as defensive technique improved).
- **Era comparisons**: Summarize how an average game in 1850 differs from one in 1950 and 2020. This could include differences in opening choice, the number of moves, material imbalance tolerance, and so on.

### 5. Scalability Considerations

As our analysis grows, we must ensure the system can scale and handle the data volume gracefully. Several strategies will be in place:

- **Transition to Database Storage**: While an in-memory dictionary approach is excellent for prototyping and speed, it might not hold billions of entries comfortably on typical hardware. We will design a path to move the data into a more scalable storage:
- **SQL Database**: We can create tables to store positions and moves. For example, a Positions table with columns (pos_hash PRIMARY KEY, fen, ...optional metadata) and a Moves table with (pos_hash, move, next_pos_hash, frequency), indexed by pos_hash for quick retrieval of moves by position. SQL systems can handle millions of rows, especially with proper indexes ￼. Complex queries (like sequences) might be slower in pure SQL, but we can fetch moves of a position quickly. We could also have a Games table for sequences or store the move-sequence tree in a normalized form (each ply as a row referencing the previous ply’s ID).
- **NoSQL / Graph Database**: A NoSQL key-value store (like Redis or LMDB) could store the POSITIONS dict on disk, using the hash as the key and a packed list of moves as the value. This would allow memory-mapped access to only needed portions. A graph database (like Neo4j or JanusGraph) could naturally model positions as nodes and moves as relationships, which might make querying patterns (like find all games reaching a position) simpler at scale. However, graph DBs have overhead; a simpler approach might be an embedded database like SQLite for positions and moves, which is easy to query from Python. There’s also ongoing work on standardized chess databases in SQL/SQLite for openness ￼, indicating this is a viable direction.
- **Hybrid Approach**: Use memory for the most common positions and sequences (e.g., all openings up to 12 moves) and offload the rest to disk. The insight here is that early-game positions are reused across many games (so keeping them in RAM gives big benefit), whereas deep unique endgames could be fetched from disk on demand.
- **Parallel and Distributed Processing**: If we need to analyze truly gigantic datasets (like including all online games or extending to billions of positions), we can distribute the workload:
- We have already considered multi-threading for parsing. Similarly, calculations on different slices of data (e.g., separate by year or by event) can be done in parallel and then merged. For instance, computing opening frequencies per decade can be farmed out to different processes for each decade’s games.
- For extremely large data (beyond a single machine’s RAM), using big data tools like Apache Spark or Dask with Python could be an option. One could store the data in a cluster and run parallel map-reduce jobs to compute statistics (this is how one analysis processed billions of Lichess games in hours ￼). Our design with position hashes and move keys would translate well to key-value based map-reduce operations.
- **Indexing Strategies**: Fast retrieval of specific patterns is key for interactive analysis. We plan the following:
- **Opening Sequence Index**: The GAMES trie is essentially an index by sequence of moves. In a database context, we might mimic this by indexing the first N moves of games. For example, an index on (move1, move2, …, moveN) in a SQL table of games can help quickly find games matching an N-move sequence. But because N can be large, a better approach is the trie or a prefix index table. We could store an MD5 or hash of the sequence up to each ply as a key in a table linking to game IDs that follow that sequence. However, this might be overkill if our in-memory trie covers the needed depth for interactive use.
- **Position Index**: If using external storage, ensure an index on the position hash for the moves table, which is straightforward (hash is key in a NoSQL, or indexed column in SQL).
- **Player/Date Index**: For trend analysis by player or time, we might create secondary indexes or data structures. E.g., a dictionary mapping years to list of game IDs (or to root nodes in the GAMES tree) so we can filter games by year range quickly, or a mapping of player name to their games’ starting nodes.
- **Handling Updates and New Data**: If we want to update the dataset (say new games from recent events), the data structures should accommodate it. The dictionaries can simply be updated by parsing new PGNs and adding to them (which is easier than updating a binary proprietary DB). In SQL/NoSQL, we’d insert new rows. The design is thus maintainable and extensible.
- **Innovative Angles in Scalability**: One idea not commonly seen in chess databases is using modern compression algorithms tailored to game trees. For example, we could try representing the GAMES tree in a single structure using a succinct tree or a specialized trie compression (like storing differential moves). Another idea is to leverage hardware - e.g., GPU acceleration for some calculations (though chess data is not inherently numeric matrix, but frequency analysis could be turned into matrix ops for GPU). These are experimental and would be considered if standard methods fall short.

## Future Work

- **Interactive Web Visualization**: Build a UI for querying historical trends.
- **Expanding to Online Chess**: Integrate real-time online chess data.
- **Advanced Data Compression**: Experiment with compressed trie structures.

## Installation & Usage

### Dependencies

```sh
pip install python-chess pandas numpy
```

### Running the Parser

```sh
python parse_pgn.py --input games.pgn --output positions.json
```

### Querying Move Frequencies

```python
from database import POSITIONS
print(POSITIONS[initial_hash])
```

## Contributing

Contributions are welcome! Please submit issues or pull requests on GitHub.

## License

GNU General Public License v3.
