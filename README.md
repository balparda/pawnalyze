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
$ [sudo] pip3 install python-chess litecli py7zr # pandas numpy
$ python3 -m pip install python-chess litecli py7zr
$ brew install db-browser-for-sqlite
```

https://python-chess.readthedocs.io/en/latest/

Use `litecli [file]` to inspect your DB. Examples:

```sql
.tables
SELECT * FROM positions LIMIT 5;
.schema positions
```

Use the https://sqlitebrowser.org/dl/ browser.

### Running the Parser

```sh
python parse_pgn.py --input games.pgn --output positions.json
```

### Querying Move Frequencies

```python
from database import POSITIONS
print(POSITIONS[initial_hash])
```

## Considerations on Chess Game Convergence at Different Ply Depths

### Ply Depth Beyond Which Games Cannot Remain Independent (Convergence is Inevitable)

As a chess game progresses deep into many moves, the odds of two games remaining completely independent (with no overlap in moves or positions) drops to essentially zero. The combinatorial explosion of possible move sequences means no two long games will randomly play out the same way, yet practical factors force convergence. In fact, no two recorded games have been identical throughout beyond roughly 30–40 moves. The enormous number of possible games (estimated at ~10^120–10^123 in total ￼) makes the chance of a full-length duplication astronomically small. By move 30 (60 ply) or beyond, some divergence is virtually guaranteed – either a different move is chosen or the games reach a common endgame position that forces a draw or repetition. For example, chess experts on forums note that no known pair of games longer than 40 moves are exactly identical ￼. Even Grandmasters who follow the same opening inevitably deviate at some point due to the vast choices available or the need to avoid known draws.

Another reason long games cannot stay fully independent is endgame convergence. As material dwindles, the game “funnels” into well-known endgame scenarios. By 60–80 moves, most games have reached basic endgames (e.g. lone kings or textbook mates) that many other games also reached. In other words, lengthy games tend to converge on a limited set of end positions (drawn king vs. king, king and pawn vs. king, etc.). Practically, if two games last extremely long, they will repeat a known endgame position or sequence, making true independence impossible. The threefold repetition and 50-move rules also limit how long a totally unique sequence can continue. In summary, beyond a certain ply depth (on the order of dozens of moves), it becomes statistically impossible for two serious games not to intersect in some way. They will either have shared opening moves, transposed into the same middlegame position, or converged on the same endgame outcome. The massive game-tree size guarantees that two long games won’t be completely distinct – eventually they hit the same chess ideas or positions. Empirical evidence supports this: no two master-level games have ever been recorded with entirely distinct move sequences all the way through once you get past the early dozens of plies.

### Ply Depth Where Independence Is Improbable but Possible (High Overlap Likelihood)

In the early to middle phase of a chess game (roughly 10–30 moves in), it is highly improbable that two games remain completely independent – yet it’s still possible in rare cases. Most games will have overlapped significantly by this stage due to popular openings and typical strategies. For instance, by 10 moves in (20 ply), a huge fraction of games are following known opening lines or common piece-development patterns. Large database studies show that many games share identical sequences in the opening:
* Openings (First 8–15 Moves): This is where move convergence is strongest. Players often follow well-trodden theory, so it’s common for games to be identical through 8, 10, or even 15 moves. Popular openings like the Ruy Lopez or Sicilian Defense yield thousands of games with the same first 10 moves. In fact, one short tactical sequence appears over 1,500 times in the ChessBase database ￼. Likewise, a well-known 16-move drawing line (repeated knight checks in a Petroff Defense) has been played at least 75 times by professionals ￼. This means up to ply 30 or so, many games are not independent – they’re literally move-for-move identical to earlier games. However, it’s improbable for two randomly chosen games to stay identical much beyond this point unless by deliberate choice.
* Middlegame (≈15–30 Moves): By the middlegame, most games start to diverge as players face unique positions. Still, partial overlap is common. Different openings can lead to similar structures (e.g. the same pawn skeleton or piece configuration), and transpositions can cause two games that began differently to reach an identical position mid-stream. Empirical data from millions of games shows high rates of position overlap. By move 20, for example, many distinct games have converged via transposition into the same middlegame position. It’s rare, but possible, for two games to remain identical this deep if players consciously follow a known line. One remarkable case is two different high-level games that were identical for the first 28 moves ￼ – an exceedingly unlikely coincidence achieved by following a long theoretical line. Another example: in a computer tournament (TCEC), two engine games followed a 2018 human game’s moves for 39 moves before diverging ￼. These cases show it’s possible to have very deep move-by-move overlap, but such events are extraordinarily uncommon. By the 20th–30th move, the vast majority of games have seen at least one differing move or unique position, making complete independence between two games improbable.
* Endgame Transpositions: In later stages (after ~30 moves), different games may converge again by reaching the same endgame. Many paths can lead to the same basic endgame position. For example, numerous games across history have all resolved into the exact same king-and-pawn vs. king scenario or the same drawn rook endgame. One study noted two tournament games that, via different move orders, arrived at the same position after 48 moves ￼ – effectively merging their narratives at that late stage. This highlights that even if the middlegames were independent, the endgames might coincide. Thus, while two games could in theory stay independent into the late middlegame, in practice they often reconverge by the end.

In summary, by the time you reach ~15–25 moves, it’s very likely two serious games have overlapped in some fashion – either by sharing an opening line or transposing into a similar middlegame. It is possible for games to stay independent (especially if players choose obscure lines), but increasingly improbable. Real-world data confirms that most games have diverged by move 15 or so (opening prep exhausted ￼), and almost all have diverged by move 30. Only a handful of extreme cases show identical play beyond 25–30 moves ￼. So while independence isn’t strictly “impossible” at, say, 20–30 ply, it is exceedingly unlikely unless the games deliberately follow the same known path.

### Chess Branching Factor and Theoretical Divergence Analysis

From a theoretical perspective, chess’s branching factor and state-space size explain these convergence phenomena. On average, a position in chess offers about 35 legal moves in the middlegame ￼ (the branching factor can be ~20 in closed opening positions and even lower in simple endgames). This high branching factor means the number of possible game sequences grows exponentially with each ply. If moves were chosen at random from all legal options, the game tree would explode in size: roughly 35^d sequences of length d on average. For example, after just 5 moves each (10 plies), the theoretical number of unique games is on the order of 10^8–10^10. Shannon famously estimated the total game-tree complexity of chess at around 10^120. Modern estimates using 35 average branching and ~80 plies (40 moves each) put it near 10^123 possible games ￼. This astronomical number dwarfs the number of games actually played in human history (on the order of millions or billions). In pure combinatorial terms, two random games have effectively zero probability of being the same sequence. Even by 15 plies, there are billions of possible positions, so random divergence is assured.

However, practical play is not random. Players gravitate toward a tiny subset of “sensible” moves, which greatly reduces the effective branching factor in practice. Moreover, many branches lead to the same positions via different move orders – a phenomenon known as transposition. This causes the theoretical explosion to collapse onto shared positions. A mathematical analysis shows that by ply 10 there are about 85 billion reachable positions, but only ~382 million of those are “uniquely reachable” by one sequence ￼. In other words, over 99% of positions at 10 plies can be arrived at via multiple distinct move orders – the game tree branches out, but then merges back when moves transpose. As depth increases, this convergence intensifies: by ply 11, there are ~726 billion possible positions, but only ~2 billion unique ones ￼. This means many different games end up in the same position by move 11, illustrating heavy overlap in the state-space despite the combinatorial growth. The effective branching factor (accounting for transpositions and sensible move pruning) is therefore much lower than the raw ~35. This is why opening books and endgame tablebases can cover so much – the vast wild game tree narrows dramatically when constrained to realistic play.

Using these models, researchers can simulate divergence probabilities. Treating an average branching factor b ≈ 35 in midgame, two random games of length d have on the order of b^d possible trajectories. The probability they’re identical is ~1/b^d (astronomically small). Even the chance they share a long prefix is tiny under uniform randomness. For instance, the odds of two random games both picking the same 15 moves is about 1 in 35^15 (~1 in 10^23!). In reality, because players often follow common lines, the observed overlap is higher – hence identical openings occur frequently. But as moves progress, player choices diversify. One analysis likened this to a “birthday paradox” in the space of chess moves: with millions of games in databases, eventually some will coincide move-for-move by chance, but beyond a certain depth the combination of choices and positions makes new deviations inevitable ￼. In practice, high-level games typically diverge by move 10–15 because optimal play has multiple nearly-equal alternatives, and humans intentionally introduce new ideas to avoid well-analyzed paths. Thus, theoretical models and database statistics agree: the “branching factor” in live play drops as players converge on good moves, but convergence of different games on the same line is short-lived – by the middlegame the explosion of possibilities takes over, and by the endgame the reduction of material forces convergence again, but into one of relatively few outcomes.

Key statistical insights include:
* State-space vs. Game-space: There are an estimated 10^46 unique chess positions ￼, but 10^123 games (move sequences). This gap is due to transpositions – many sequences lead to the same position. So while game sequences explode combinatorially, the state-space “only” grows about 10^3–10^4 per ply initially, before transposition effects.
* Average Branching: ~35 in typical positions ￼. It tends to be lower in locked pawn structures or simple endgames (often < 10 moves available in trivial endgames), and can be higher in wild tactical positions. An average game might have 30–40 legal moves early on, then maybe 20–30 in a constrained middlegame, and perhaps 15 or fewer in an endgame. This means the game tree actually fans out more slowly once pieces come off the board (some research even finds a local maximum in branching when around 5–6 pieces remain, due to open board mobility ￼ ￼, but ultimately with very few pieces the total moves are limited). Overall, the high midgame branching ensures divergence of most game trajectories.
* Empirical Game Overlap: Using large databases (Lichess, Chess.com, FIDE archives), we see that nearly all games separate by move 15. One database study found that opening explorers provide “useful advice” only up to around move 8–15 on average ￼ – beyond that, the frequency of any given sequence drops off. Indeed, while thousands of games might share a 10-move sequence, virtually none share a 30-move sequence unless forced. The existence of even two games identical at 28 moves or more ￼ is notable and usually due to known theoretical lines or deliberate repetition.

In conclusion, both data and theory indicate that as ply depth increases, the likelihood of two games being truly independent passes from unlikely to effectively impossible. Early on, the wealth of opening theory causes games to cluster together (reducing independence), but once that forest of theory is left, the combinatorial explosion of the chess tree takes over, making each game unique. By the time extreme ply depths are reached, games have either diverged long before or reconverged into a common ending. The net result is that no two long games are independent – they will have converged at some point – and even moderate-length games rarely avoid converging on at least some moves or positions. These conclusions are backed by analyses of millions of games and the known branching-factor models of the chess game tree ￼ ￼.

Sources: Real-world chess database statistics (Lichess, ChessBase) and academic analyses were used to support these conclusions. For example, ChessBase reports thousands of instances of identical short games ￼, while Stack Exchange and Chess.com discussions have documented the rare cases of long move-sequence overlaps ￼ ￼. Theoretical values like the ~10^123 game complexity and ~35 average branching factor come from computational chess research ￼ ￼. These empirical and theoretical sources collectively illustrate how game convergence behavior changes with ply depth, from frequent overlap in openings to almost guaranteed divergence (or eventual merging into known endgames) by the time we reach the deeper plies of a chess game.

## Contributing

Contributions are welcome! Please submit issues or pull requests on GitHub.

## License

GNU General Public License v3.
