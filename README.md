# PDF-FPSE: the PDF similarity checker

## 1. What this app does

You give the app a folder of PDF files.

The app compares **every PDF with every other PDF**. It looks for two things:

1. **The same text**, written in the same order.
2. **The same screenshot** (picture).

Then, for each pair of PDFs, the app gives one of three results:

| Result | What it means |
|---|---|
| **Copied** | Strong signs that the two PDFs share text. A person should read both. |
| **Needs review** | Some signs. A person should take a look. |
| **No evidence** | Nothing unusual found. |

> **Please remember.** The app only points at suspicious pairs. It cannot prove that someone copied. A person must open both PDFs and read the matching text. The fixed numbers in the app (the "constants") were chosen by judgment and were only tested on made-up sample text. Test the app on PDFs where you already know the answer before you trust it.

---

## 2. Words you will see in this file

| Word | Simple meaning |
|---|---|
| **Pair** | Two different PDFs that are compared with each other. |
| **Phrase** | 3 words in a row. Example: `select name from`. |
| **Run** | A group of words that is exactly the same in both PDFs of a pair, in the same order. A run of 20 words means 20 identical words in a row. |
| **Chance** | Something that happens by accident, with nobody copying. Two PDFs about the same subject always share some words and short phrases by chance. |
| **p-value** | A number from 0 to 1. It answers one question: *"If the two students worked alone, how likely is it that their PDFs match this much?"* A **small** p-value means "very unlikely". Example: 0.001 means about 1 time in 1,000. |
| **q-value** | A p-value that has been made stricter, because the app checks many pairs. Small means suspicious. |
| **Constant** | A fixed number written in the program. |

---

## 3. How to install and use the app

**Install**

1. Install Python 3.10 or newer.
2. Put `app.py`, `engine.py` and `requirements.txt` in one folder.
3. Open a command window in that folder and type: `pip install -r requirements.txt`
   (If that does not work, type: `python -m pip install -r requirements.txt`)
4. Start the app: `python app.py`

**Use**

1. Click **Browse** next to *Student PDFs folder* and choose the folder.
2. Choose where to save the reports.
3. *Optional:* choose an *Assignment prompt* file (`.txt` or `.pdf`) that holds the question text. The app ignores any phrase found in that file.
4. Click **Check for similarity**.
5. Double-click a row to see all the numbers and the longest matching passage.
6. Click **Open reports folder** to open the CSV files.

**Use one folder for one assignment.** If you mix different assignments, the app learns the wrong idea of what is normal.

---

## 4. The 12 steps in one table

| Step | What the app does | What comes out |
|---|---|---|
| 1 | Reads the PDFs | Text and pictures |
| 2 | Cuts the text into words | A word list for each PDF |
| 3 | Finds phrases that are too common to count | A list of usable positions |
| 4 | Finds runs shared by two PDFs | A run list for each pair |
| 5 | Learns what a normal amount of matching is | Three things: the rates, the decay and phi |
| 6 | Calculates the text p-value | One p-value for each pair |
| 7 | Compares the screenshots | A match percent for each pair |
| 8 | Calculates the image p-value | One p-value for each pair |
| 9 | Joins the two p-values | One combined p-value |
| 10 | Makes the p-values stricter | One q-value for each pair |
| 11 | Decides the result | Copied / Needs review / No evidence |
| 12 | Writes the reports | Two CSV files and the table |

Number of pairs: if there are **N** PDFs, then pairs = N × (N − 1) ÷ 2.
Example: 30 PDFs give 30 × 29 ÷ 2 = **435 pairs**.

### The statistical methods used in each step

| Step | Method(s) used | What it gives |
|---|---|---|
| 3 | Document-frequency filtering | Which phrases to ignore |
| 4 | Maximal run counting | One event for each copied passage |
| 5 | Leaving out extreme pairs, observed rate (events ÷ opportunities) with a floor, geometric decay, Pearson dispersion factor (phi) | The chance model of the class |
| 6 | Poisson right-tail probability, negative binomial distribution, scan over run lengths with a Bonferroni correction | The text p-value |
| 7 | Median per pixel, absolute-difference limit, agreement proportion | The image match |
| 8 | Robust z-score (median and MAD), normal right-tail probability | The image p-value |
| 9 | Fisher's combined probability test (chi-square distribution) | One combined p-value |
| 10 | Benjamini–Hochberg false discovery rate | The q-value |
| 11 | Significance limits and a minimum-length rule | The result |

Steps 1, 2 and 12 only read, cut up and write data, so they use no statistical formula. Under each step below you will find a part called "Method used here, and why".

---

## 5. The example used in this file

From Step 4 onwards, every step is explained with the **same small example class**, so you can follow one pair from start to finish.

> **All numbers in the examples are example numbers made up to show how the steps work. They are not output from real files.**

- The class has **5 PDFs**: `S1.pdf` to `S5.pdf`. Each has about 1,000 words and one screenshot.
- That gives **10 pairs**.
- The pair we follow is **S2 and S4**. In our example, S4 copied a passage and the screenshot from S2.

---

## 6. Step 1: Read the PDFs

**What goes in:** the PDF files in the folder.

**What the app does:**

1. It opens every PDF. A PDF that cannot be opened is skipped and named in the summary line. The app needs at least 2 readable PDFs.
2. It reads the text in blocks. If the **middle** of a block is in the top 7% or bottom 7% of the page, the block is skipped. Headers, footers and page numbers are there.
3. It collects the pictures. A picture is kept only if its **shorter side is at least 80 pixels**. A picture that appears many times in one PDF is used once.
4. Each kept picture is turned into grey shades and resized to **512 × 320 pixels**. The app also remembers its shape (width ÷ height).

**What comes out:** for each PDF, its text and its small grey pictures.

**Constants and why:**

| Constant | Value | Why |
|---|---|---|
| `MARGIN` | 7% | Headers, footers and page numbers are in this border. The app checks the *middle* of a block, so a normal paragraph that touches the border is kept. |
| `MIN_IMG_PX` | 80 pixels | Smaller pictures are icons and bullets, not screenshots. |
| `IMG_SIZE` | 512 × 320 | Pictures must have the same size so pixels can be compared. This size keeps the shape of text and is still fast. |

---

## 7. Step 2: Cut the text into words

**What goes in:** the text of one PDF.

**What the app does:**

1. It changes all letters to small letters.
2. It cuts the text wherever there is a space or a mark such as `. , ; : ! ? ( ) [ ] { } " ' / = + *`.
3. Letters, digits and underscores stay inside words. So `student_id`, `5` and `select` are all words. Any language works.

**What comes out:** a list of words for each PDF. The number of words in the list is called **n**. (In our example, n = 1,000 for every PDF.)

**Why:** two PDFs can only match if their words are written in the same form. Digits are kept because `WHERE id = 5` is real content in SQL.

---

## 8. Step 3: Find phrases that are too common to count

Some phrases are in many PDFs for normal reasons, such as the assignment question or a standard heading. These must not count as evidence.

**What goes in:** the word lists of all PDFs, and the optional prompt file.

**What the app does:**

1. It takes every **phrase** (3 words in a row) and notes where it is in each PDF.
2. For each phrase it counts **how many PDFs contain it**. Call this the *file count*.
3. A phrase is **common** if:
   - its file count is bigger than a limit called `rare_max`, **or**
   - it is found in the prompt file.
4. Every word position whose phrase is **not** common is marked **usable**.

**The formula for `rare_max`:**

```
rare_max = min( max(3, ceil(0.15 × N)) ,  max(N − 1, 2) )
```

What the words mean:
- **N** = number of PDFs.
- **ceil** = round up to a whole number. (`ceil(4.5)` = 5)
- **max(a, b)** = the bigger of the two numbers.
- **min(a, b)** = the smaller of the two numbers.

| PDFs (N) | rare_max | In words |
|---|---|---|
| 2 | 2 | Nothing is common (only the prompt is ignored). |
| 3 | 2 | A phrase in all 3 PDFs is common. |
| 4 | 3 | A phrase in all 4 PDFs is common. |
| 5 | 3 | A phrase in 4 or 5 PDFs is common. |
| 10 | 3 | A phrase in 4 or more PDFs is common. |
| 30 | 5 | A phrase in 6 or more PDFs is common. |

**Our example:** N = 5, so `rare_max = min( max(3, ceil(0.75)), max(4, 2) ) = min(3, 4) = 3`. A phrase found in **more than 3** of the 5 PDFs is common and is ignored.

**Why this formula:**
- `0.15 × N`: a phrase in more than about 15 out of 100 PDFs is normal wording.
- `max(3, …)`: a group of 3 students who share a passage must still be found.
- `min(…, max(N − 1, 2))`: with 3 or more PDFs, a phrase found in **all** of them is always common.

**What comes out:** a list of *usable* positions in each PDF.

**About the prompt:** the match is on exact 3-word phrases. A question that was reworded is not removed.


### Method used here, and why

**Name: document-frequency filtering.** This is a counting rule, not a probability formula. The app counts in how many PDFs each phrase appears, and it ignores phrases that appear in too many.

**Why the app does this:**

- The later steps treat a shared phrase as a *surprising* event. A phrase that most PDFs contain is not surprising. If it stayed in, normal pairs would look suspicious, and Step 5 would learn a wrong idea of what is normal.
- **Why the limit grows with the class (`0.15 × N`):** in a bigger class, more PDFs use the same normal wording by chance. So the limit must rise with the number of PDFs.
- **Why the limit is never below 3:** if the limit were 2, a phrase shared by 3 students who copied from each other would be thrown away as "common", and the copying would be hidden.
- **Why the limit stays below N when there are 3 or more PDFs (`max(N − 1, 2)`):** a phrase that is in every PDF can never be evidence about one particular pair.

---

## 9. Step 4: Find shared runs

**What goes in:** the phrase positions of two PDFs, called A and B.

**What the app does:**

1. It lists every phrase that is in both A and B, with its position in A and its position in B.
2. If a phrase matches at position *i* in A and *j* in B, and the **next** phrase matches at *i + 1* in A and *j + 1* in B, both belong to **one run**. The app joins them.
3. The length of a run in words is: `(number of joined phrases) + 2`.
4. A run is **kept** only if at least one of its positions is *usable* (see Step 3). A run made only of common phrases is thrown away.
5. A phrase that would create more than 2,500 matching position pairs is skipped. This protects the app from very repetitive text, such as a long row of dashes.

**A tiny example of how one run is built.** Say S2 and S4 contain these words:

- S2: `the(0) table(1) stores(2) student(3) records(4) in(5) rows(6) and(7) columns(8)`
- S4: `a(0) database(1) table(2) stores(3) student(4) records(5) in(6) rows(7) and(8) columns(9) of(10) data(11)`

The numbers in brackets are word positions. The app cuts both into 3-word phrases and finds the phrases that are in both:

| Shared phrase | Position in S2 | Position in S4 |
|---|---|---|
| table stores student | 1 | 2 |
| stores student records | 2 | 3 |
| student records in | 3 | 4 |
| records in rows | 4 | 5 |
| in rows and | 5 | 6 |
| rows and columns | 6 | 7 |

Each match moves **one step forward in both PDFs at the same time**. So the app joins all 6 matches into **one run**. Its length is `6 + 2 = 8 words`: *table stores student records in rows and columns*.

**Now the real pair S2–S4.** The app finds these runs in all the text:

| Run | Length in words |
|---|---|
| The copied passage | **42** |
| Other runs | 6, 5, 4, 3, 3 |

The app also found one run, *the primary key of* (4 words). But those phrases are in **4 of the 5 PDFs**. 4 is more than `rare_max = 3`, so they are common, and the app **throws that run away**.

**What comes out:**
- Runs = 42, 6, 5, 4, 3, 3
- **`Longest_Match_Words`** = the longest run = **42**
- **`Shared_Words`** = the total length of all runs that are 4 words or longer = 42 + 6 + 5 + 4 = **57**. (If two runs overlap, some words can be counted twice.)

**Why runs and not phrases:** the copied passage of 42 words contains 40 overlapping phrases. Those 40 phrases are **one** event, not 40 separate pieces of evidence. Counting runs counts each copied passage once. This makes the probability calculation in Step 6 correct.


### Method used here, and why

**Name: maximal run counting.** The app joins matching phrases that sit next to each other in both PDFs into one **run**, and it makes each run as long as possible ("maximal"). The length of a run is `(joined phrases) + 2`.

**Why the app does this:**

- **Why runs, not single phrases:** Step 6 uses the Poisson formula. That formula is only correct when the events it counts are *separate* from each other. Overlapping phrases are not separate. The 42-word copied passage in S2–S4 contains 40 overlapping phrases, and they are really **one** event. Counting 40 events would make the p-value far too small. Counting 1 run is correct.
- **Why "maximal" (as long as possible):** if the app cut one copied passage into several shorter runs, it would count one copy as several events. Joining everything that continues in both PDFs counts each passage once.
- **Why `+ 2`:** a phrase uses 3 words. Each next matching phrase moves one word forward, so it adds only **one** new word. So `k` joined phrases cover `3 + (k − 1) = k + 2` words. Example: 6 joined phrases give 8 words.
- **Why runs with no usable position are thrown away:** a run made only of common phrases says nothing about this pair (see Step 3).

---

## 10. Step 5: Learn what is normal in this class

To say "this pair matches too much", the app first needs to know **how much matching is normal**. It learns this from the PDFs in the folder.

**What goes in:** the runs of **all** pairs, and the word counts (n and m) of the two PDFs in each pair.

**What the app does:**

### 5a. Choose the normal pairs

Pairs that have a run of **15 words or longer** are left out. They are probably copied, and they must not change what "normal" means. If fewer than 3 pairs are left, all pairs are used.

**Our example:** S2–S4 has a run of 42 words, so it is left out. The other **9 pairs** are the normal pairs. Each has `1,000 × 1,000 = 1,000,000` position pairs (the number of ways to put a word of one PDF next to a word of the other). Together, the 9 pairs have **9,000,000** position pairs.

### 5b. Measure the chance rate

For each run length `l` from 3 to 14, the app works out:

```
rate(l) = (number of runs of l words or longer in all normal pairs)
          ÷ (total position pairs of all normal pairs)
```

`rate(l)` means: how many runs of `l` words or longer appear **by chance** for each position pair.

**Our example:**

| Length l | Runs found in the 9 normal pairs | rate(l) = runs ÷ 9,000,000 |
|---|---|---|
| 3 | 450 | 0.00005 |
| 4 | 180 | 0.00002 |
| 5 | 72 | 0.000008 |
| 6 | 27 | 0.000003 |
| 7 | 12 | 0.00000133 |
| 8 | 5 | 0.000000556 |
| 10 | 2 | 0.000000222 |
| 14 | 0 | 0.0000000556 (see the floor below) |

At length 14, nothing was found, and that would give 0. The app never uses 0. It uses the **floor**: `0.5 ÷ 9,000,000 = 0.0000000556`. A rate is also never bigger than the rate of the next shorter length, because a longer run cannot be more common than a shorter one.

### 5c. Measure the decay

Above 14 words there are normally no chance runs to count. So the app measures how fast the rate falls for each extra word. This is the **decay**:

```
decay = ( rate(10) ÷ rate(6) ) ^ 0.25
```

`^ 0.25` means the fourth root. The length goes from 6 to 10, which is 4 extra words, so the answer is the change **for each extra word**.

**Our example:** `(0.000000222 ÷ 0.000003) ^ 0.25 = (2 ÷ 27) ^ 0.25 ≈ 0.52`. Each extra word makes a chance run about 2 times less likely.

The decay is kept between **0.05 and 0.7**. If there are almost no chance runs to measure, the app uses **0.3**.

For a length above 14, the app uses:

```
rate(l) = rate(14) × decay ^ (l − 14)
```

**Our example:** `rate(42) = 0.0000000556 × 0.52^28 ≈ 0.00000000000000068`.

### 5d. Measure phi

Some pairs share more by chance than other pairs. The app measures how much the pairs differ from each other. This number is called **phi**.

- The app starts at length 8 and goes down to the first length where the **total expected count is at least 10**.
- For that length it works out, for every normal pair, the number it **expected** (`n × m × rate(l)`) and the number it **found**. Then:

```
phi = the bigger of ( 1 ,  sum of (found − expected)² ÷ sum of expected )
```

- **phi = 1** means the pairs differ only as much as chance allows.
- **phi above 1** means the pairs differ more. The app then becomes more careful in Step 6.

**Our example:** at length 8 the total expected count is 5, which is too small. At length 7 it is 12, so the app uses length 7. For each normal pair, expected = `1,000,000 × 0.00000133 = 1.33`. The 9 pairs actually had 2, 0, 1, 3, 1, 0, 2, 1, 2 runs. The sum of (found − expected)² is 8.0 and the sum of expected is 12. So `phi = the bigger of (1, 8.0 ÷ 12) = the bigger of (1, 0.67) = 1`.

**What comes out of Step 5:** the table of `rate(l)`, the `decay` (0.52) and `phi` (1).

**Constants and why:**

| Constant | Value | Why |
|---|---|---|
| `EMP_MAX` | 14 words | For lengths up to 14, a class usually has enough chance runs to count. Longer ones are too rare to count. (A judgment, not a calculation.) |
| Copy screen | 15 words | A run this long is almost never chance, so the pair is not used to learn what is normal. |
| Floor | 0.5 ÷ (total position pairs) | Gives every length a small chance rate above zero. |
| Decay limits | 0.05 and 0.7 | Below 0.05 would make long runs look impossible. Close to 1 would make every long run look normal. |
| `DEFAULT_DECAY` | 0.3 | Used only when the decay cannot be measured. |


### Methods used here, and why

Step 5 uses four named methods. Each one is explained below.

**(a) Name: leaving out extreme pairs (robust estimation).**
*What it is:* pairs with a run of 15 words or longer are not used to learn the chance rates.
*Why:* the aim of Step 5 is to learn how much matching happens **by chance**. A copied pair is not chance. If it stayed in, it would make "normal" look more matching than it really is, and the app would then miss the copied pair, and other copied pairs too. Leaving it out makes the chance rates depend on the ordinary pairs only. This also works when several pairs are copied (for example a group of 3 students).

**(b) Name: observed rate = events ÷ opportunities (with a floor).**
*The formula:* `rate(l) = (runs of l words or longer) ÷ (total position pairs)`.
*Why this formula:*
- A run of `l` words or longer can start at any place where a word of PDF A is lined up with a word of PDF B. So each position pair is one **opportunity** for a run to start. A pair of PDFs with n and m words has `n × m` opportunities.
- The Poisson formula in Step 6 needs "the chance per opportunity". The best estimate of that chance from data is simply: events counted ÷ opportunities counted.
- All normal pairs are added together before dividing. This is right because a bigger PDF has more opportunities, so it should count for more.
- **Why the floor `0.5 ÷ (total position pairs)`:** if a run length was never seen, the count is 0, and a rate of 0 would mean "this can never happen by chance". That claim is too strong, because the app only looked at a limited number of position pairs. Using half an event is a common small correction when a count is zero. It is a convention, not a measured value.
- **Why a rate is never larger than the rate of the next shorter length:** every run of 10 words is also a run of 9 words, so there can never be more long runs than short runs.

**(c) Name: geometric decay (the decay factor).**
*The formula:* `decay = (rate(10) ÷ rate(6)) ^ 0.25`, and for a length above 14: `rate(l) = rate(14) × decay ^ (l − 14)`.
*Why this formula:*
- Each extra word in a run must also match. If the chance that "one more word matches" is about the same each time, then every extra word multiplies the chance by the same factor. This kind of fall is called **geometric**.
- From 6 words to 10 words there are 4 extra words. So `rate(10) ÷ rate(6)` is the factor for 4 steps. Taking the fourth root (`^ 0.25`) gives the factor for **one** step. (This is the geometric mean of the four steps.)
- **Why 6 and 10:** short runs of 3 or 4 words are mostly common phrases, and they do not fall like longer runs. At 6 to 10 words there are still enough counts to measure, and the lengths are far enough from 3 and 4.
- **Why the limits 0.05 and 0.7:** a decay below 0.05 would make long runs look impossible. A decay near 1 would make every long run look normal.
- **Why this is needed at all:** above 14 words there are too few chance runs to count, so the rate must be extended from the shorter lengths. This is an **assumption** of the app, and it is the main reason the p-values for very long runs are so small.

**(d) Name: dispersion factor phi (Pearson dispersion statistic).**
*The formula:* `phi = the bigger of (1, sum of (found − expected)² ÷ sum of expected)`.
*Why this formula:*
- For a pure Poisson count, the squared difference `(found − expected)²` is on average equal to `expected`. So the ratio of the two sums is about **1** when the pairs vary only as much as chance allows.
- If some pairs match more than others for ordinary reasons (for example because the writers use the same words), the pairs vary **more**, and the ratio is above 1. The more it is above 1, the more careful the app must be.
- **Why `the bigger of (1, …)`:** the app is never allowed to be *less* careful than the plain Poisson formula.
- **Why the longest length with an expected total of at least 10:** the long runs are the ones that matter for Step 6, so the spread is measured at the longest length that has enough counts to be stable.

---

## 11. Step 6: The text p-value

**What goes in:** the runs of one pair, the word counts n and m, and the numbers from Step 5.

**What the app does:**

1. It lists the different run lengths in this pair that are **4 words or longer**. The number of different lengths is called **K**. (Runs of 3 words happen by chance so often that they are not tested. This is the constant `MIN_TEST_WORDS = 4`.)
2. For **each** length `l` in the list it works out:
   - **c** = how many runs of `l` words or longer this pair has.
   - **λ** (say "lambda") = `n × m × rate(l)` = how many such runs we **expect by chance** between these two PDFs.
   - The **chance of getting c or more** runs. This is a p-value for this length.
3. It takes the **smallest** of these chances and multiplies it by **K**. If the answer is more than 1, it uses 1.

**Why multiply by K:** if the app tries several lengths and keeps the best one, it gets more chances to find something by luck. Multiplying by K takes that advantage away. (This is called a Bonferroni correction.)

**How the chance of "c or more" is worked out.** If phi is 1, the app uses the **Poisson formula**. It is the standard formula for counting events that are rare and independent:

```
chance of exactly i runs = e^(−λ) × λ^i ÷ i!
chance of c or more      = 1 − (the chances of exactly 0, 1, 2, … , c−1 runs added together)
```

- **e** is the number 2.718…
- **i!** means `1 × 2 × 3 × … × i`. (3! = 6)

If phi is above 1, the app uses a wider version of the same idea, called the **negative binomial** formula. It has the same average λ, but its spread is `phi × λ`. Its two settings are `size = λ ÷ (phi − 1)` and `p = 1 ÷ phi`. It gives a bigger chance for big counts, so the app is more careful.

**Our example** (S2–S4, phi = 1, so the Poisson formula is used):

- Lengths of 4 or more in this pair: **42, 6, 5, 4**. So **K = 4**.
- Each position pair count is `n × m = 1,000,000`.

| l | c (runs of l or longer in S2–S4) | λ = 1,000,000 × rate(l) | Chance of c or more |
|---|---|---|---|
| 4 | 4 | 20 | about 1.0 |
| 5 | 3 | 8 | `1 − (0.0003 + 0.0027 + 0.0107)` = about 0.99 |
| 6 | 2 | 3 | `1 − (0.0498 + 0.1494)` = about 0.80 |
| **42** | **1** | **0.00000000068** | **about 0.00000000068** |

The first three rows are big numbers. Runs of 4, 5 and 6 words are normal in this class. The 42-word run is not.

The smallest chance is 0.00000000068. Multiply by K = 4:

```
Text_P_Value = 4 × 0.00000000068 ≈ 0.0000000027    (2.7 × 10⁻⁹)
```

**Why a short run says nothing:** if S2 and S4 had only a 7-word run, then `λ = 1,000,000 × 0.00000133 = 1.33`. The chance of 1 or more is `1 − e^(−1.33) = 0.74`. That is a big number, so the app finds nothing suspicious.

**What comes out:** `Text_P_Value` for the pair. For S2–S4 it is about 2.7 × 10⁻⁹.


### Methods used here, and why

Step 6 uses four named methods.

**(a) Name: expected count (`λ = n × m × rate(l)`).**
*Why this formula:* `n × m` is the number of opportunities, and `rate(l)` is the chance of a run for each opportunity. Opportunities × chance per opportunity = the number of runs the app **expects by chance** between these two PDFs. For S2–S4 and length 6: `1,000,000 × 0.000003 = 3`. So the app expects 3 chance runs of 6 words or longer, and S2–S4 has 2, which is normal.

**(b) Name: Poisson distribution, right-tail probability.**
*The formula:* `chance of exactly i runs = e^(−λ) × λ^i ÷ i!`, and the p-value is `1 − (the chances of exactly 0, 1, … , c−1 runs added together)`.
*Why this formula:*
- The Poisson distribution gives the chance of each count (0, 1, 2, …) when events are **rare**, **separate** from each other, and happen with a steady average (λ). A shared run is such an event: there are very many opportunities (`n × m`), and each one has a tiny chance. This is exactly the case where the Poisson formula is accurate. (Step 4 made the runs separate events.)
- **Why "c or more" and not "exactly c":** the chance of exactly the observed count is small even for a normal pair. Example: if 1.33 runs are expected, the chance of exactly 1 run is `e^(−1.33) × 1.33 = 0.35`, but that is still normal. The useful question is "how likely is this many **or more**?", because that tells how extreme the pair is. This is called the **right-tail** probability.
- **Why the 1 − (…) form:** adding up the chances of 0, 1, … , c−1 runs gives the chance of *fewer than c* runs. One minus that is the chance of *c or more*.
- **What the parts do:** `λ^i ÷ i!` is larger when λ is large, and `e^(−λ)` makes all the chances add up to exactly 1.

**(c) Name: negative binomial distribution (used when phi is above 1).**
*The settings:* `size = λ ÷ (phi − 1)` and `p = 1 ÷ phi`.
*Why this formula:*
- The Poisson formula assumes every pair has the same chance. In real classes, some pairs have a higher chance than others. The negative binomial distribution is what you get when a Poisson count has an average that **varies from pair to pair**. It has a fatter tail, so it gives bigger probabilities for big counts.
- The two settings are chosen so that the **average stays λ** and the **spread becomes `phi × λ`**. (For this distribution, the average is `size × (1 − p) ÷ p`, and the spread is the average ÷ p. With `p = 1 ÷ phi` the spread is `phi` times the average, and `size = λ ÷ (phi − 1)` keeps the average equal to λ.)
- When phi is 1, there is nothing extra to allow for, and the plain Poisson formula is used.

**(d) Name: scan over run lengths with a Bonferroni correction (multiply by K).**
*Why scan over lengths:* some copying is one long passage (long `l`, small `c`), and some is many medium passages (short `l`, large `c`). Testing every length that appears in the pair catches both kinds.
*Why multiply by K:* the app tries K lengths and keeps the smallest probability. Trying K times gives K chances to get a small value by luck. The chance that at least one of K tests gives a value of `x` or smaller is at most `K × x`. So multiplying the smallest value by K makes the final p-value honest. If the result is above 1, it is set to 1, because a probability cannot be larger than 1.

---

## 12. Step 7: Compare the screenshots

Many students use the same program, so their screenshots have the same window, menus and buttons. If the app compared the whole picture, every pair would look alike. So the app compares only each picture's **own content**, for example the query and the result rows.

**What goes in:** the small grey pictures from Step 1 and their shapes.

**What the app does:**

1. **Group** the pictures that have nearly the same shape.
2. **Make a typical picture for each group.** If the group has pictures from **at least 3 different PDFs**, then for every pixel the app takes the **middle value** over all the pictures. (The middle value is the one in the center when you sort the numbers.) This typical picture shows what all the screenshots share. If the group has fewer than 3 PDFs, the app uses the most common grey value of each picture instead (its background).
3. **Find the own content.** A pixel is **own content** if it differs from the typical picture by **more than 30 grey levels**. (The grey scale goes from 0 to 255.)
4. **Compare two pictures** (one from each PDF of a pair, with shapes that differ by at most 0.05):
   - Collect the pixels that are own content in **either** picture. Call them the *used pixels*.
   - If the used pixels are fewer than 0.3% of the picture, skip this pair of pictures. They have nothing of their own to compare.
   - Otherwise work out:

```
match = (used pixels where the two pictures differ by 30 or less)
        ÷ (all used pixels)
```

5. If a pair of PDFs has several picture pairs, the **best** match is kept.

**Our example:**

- All 5 pictures are in one group and come from 5 different PDFs, so the app builds the typical picture from the middle value of each pixel.
- Each picture has 512 × 320 = 163,840 pixels.
- S2's own content: 2,500 pixels. S4's own content: 2,600 pixels.
- Used pixels (own content in either): **4,000**. This is more than 0.3% of 163,840 (that is about 491), so the pair is compared.
- Of the 4,000 used pixels, **3,900** differ by 30 or less between S2 and S4.
- `match = 3,900 ÷ 4,000 = 0.975`.

**What comes out:** `Image_Match_Percent` = match × 100 = **97.5** for S2–S4. It is empty if a pair has no pictures that can be compared.

The other 9 pairs score between 0.15 and 0.25, because their screenshots only share the program window.

**Constants and why:**

| Constant | Value | Why |
|---|---|---|
| `IMG_TOL` | 30 grey levels | Resizing and saving as JPEG change pixels by a few levels. 30 allows that, but a different letter changes a pixel by much more. |
| Shape step and limit | 0.05 | Pictures with different shapes are stretched differently, so they cannot be compared pixel by pixel. |
| Group size | 3 PDFs | The middle value needs several pictures to mean something. |
| `MIN_MASK` | 0.3% | Text screenshots have only a small part that is dark. This limit lets normal screenshots be compared, but skips pictures that are almost empty. |


### Methods used here, and why

Step 7 uses four simple methods. They are not probability formulas, but each one is chosen for a reason.

**(a) Name: median of each pixel (the typical picture).**
*Why the median and not the average:* the average is pulled by an unusual picture. If one PDF has a very different screenshot, the average of that pixel changes for everybody. The median (the middle value after sorting) does not change much, as long as most pictures share the same window. This keeps the typical picture equal to "what all the screenshots share".
*Why at least 3 PDFs:* with only 1 or 2 pictures, the "middle" is just one of them (or the average of both), so it cannot show what is shared.

**(b) Name: absolute difference with a limit (`|pixel − typical| > 30`).**
*Why:* only the **size** of the change matters, not whether the pixel became lighter or darker, so the absolute value is used. The limit of 30 ignores tiny changes caused by resizing and JPEG saving. A pixel that differs by more than 30 is real content, such as a letter.

**(c) Name: agreement proportion (`match = agreeing used pixels ÷ used pixels`).**
*Why this formula:*
- A **proportion** is a number between 0 and 1 that is easy to read: 0.975 means 97.5% of the content agrees.
- **Why only the used pixels:** the picture has a large empty background and a shared window. These agree in every pair. If they were counted, every pair would get a match close to 100%, and the number would say nothing. Only the pixels that carry content are compared.
- **Why "own content in *either* picture":** if a pixel has content in one picture and not in the other, the two pictures disagree there, and it must be counted as a disagreement. Using only pixels with content in *both* pictures would let a picture with extra content still match 100%.

**(d) Name: best match over all picture pairs.**
*Why:* one reused screenshot is enough to matter, so a PDF pair is judged by its **best** picture pair.

---

## 13. Step 8: The image p-value

**What goes in:** the `Image_Match_Percent` of every pair that has one (as a number from 0 to 1).

**What the app does:**

**If fewer than 8 pairs have an image match,** the app does not have enough data for a statistical test. It uses a **fixed rule** instead: a match of **0.92 or more** counts as "the same picture".

**Otherwise,** it does a **robust z-test**:

```
middle = the middle value of all image matches in the class
MAD    = the middle value of the distances |match − middle|
spread = the bigger of ( 1.4826 × MAD ,  0.03 )
z      = (match − middle) ÷ spread
p      = the chance of a normal-curve number being bigger than z
```

- **middle** and **MAD** (median absolute deviation) describe "typical" and "how much it usually varies". A few extreme values do not change them, so a copied screenshot does not change what "typical" means.
- **1.4826** makes the MAD comparable to the usual measure of spread (the standard deviation).
- A match below **0.75** is not tested and gets p = 1.
- p is never allowed to be below 10⁻³⁰⁰.

**Our example:** the 10 image matches are 0.15, 0.17, 0.18, 0.19, 0.20, 0.21, 0.22, 0.23, 0.25 and **0.975**. That is 10 matches, which is 8 or more, so the app uses the z-test.

```
middle = (0.20 + 0.21) ÷ 2 = 0.205
MAD    = the middle of the distances = 0.025
spread = the bigger of (1.4826 × 0.025, 0.03) = the bigger of (0.037, 0.03) = 0.037
z      = (0.975 − 0.205) ÷ 0.037 ≈ 20.8
```

A z of 20.8 gives an image p-value of about **4 × 10⁻⁹⁶**. That is almost zero.

The other 9 pairs have matches below 0.75, so they are not tested and get **p = 1**.

**What comes out:** an image p-value for every pair that has an image match. It is used in Step 9 and is not shown as its own column.

**Constants and why:**

| Constant | Value | Why |
|---|---|---|
| `IMG_MATCH` | 0.92 | Used only when there are too few images for a test. In a test, different screenshots from the same program scored under 20%, and a reused screenshot scored 100%. 92% is far above normal and still allows for small changes. |
| `IMG_MIN` | 0.75 | A weak match is never called suspicious. |
| Smallest spread | 0.03 | Stops the test from treating a tiny difference as important when almost all matches are nearly equal. |
| Fewest image matches | 8 | Below 8, the middle and the spread are not trustworthy. |


### Methods used here, and why

**Name: robust z-score (median and MAD).**
*The formulas:* `middle = median of all matches`, `MAD = median of |match − middle|`, `spread = 1.4826 × MAD` (at least 0.03), `z = (match − middle) ÷ spread`.

**Name: normal right-tail probability.** The p-value is the chance that a number from the normal ("bell") curve is bigger than `z`.

**Why these formulas:**

- **What a z-score does:** it says how many "spreads" a match is above the typical match. A z of 20.8 means 20.8 spreads above typical. This turns "97.5% match" into a number that has a probability.
- **Why median and MAD, not the average and the usual standard deviation:** the average and the standard deviation are pulled by extreme values. A copied screenshot with a match of 0.975 would raise the average and make the spread much bigger, and then it would look *less* unusual. The median and the MAD are not changed much by a few extreme values, so the copied screenshot cannot hide itself.
- **Why 1.4826:** for normally spread numbers, the MAD equals about 0.6745 times the usual spread. Dividing by 0.6745 (the same as multiplying by 1.4826) turns the MAD into the usual spread.
- **Why the bell curve:** it is the standard way to change a z-score into a probability.
- **Why only the right tail:** only a match that is **higher** than typical is suspicious. A low match is not.
- **Why the spread is at least 0.03:** if almost all matches are nearly equal, the MAD is close to 0. Then even a small difference would give a huge z. The minimum stops this.
- **Why a match below 0.75 gets p = 1:** a weak match is never suspicious, even when the class is very uniform.
- **Why the fixed 0.92 rule when there are fewer than 8 matches:** the middle and the spread cannot be trusted with so few numbers.
- **Limit of this method:** it assumes the ordinary matches are roughly bell-shaped. This is not exactly true, so the image p-value is a ranking aid and not an exact probability.

---

## 14. Step 9: Join the two p-values

**What goes in:** the text p-value, and the image p-value if the pair has one.

**What the app does:** if both exist, it joins them with **Fisher's method**:

```
X = −2 × ( ln(p_text) + ln(p_image) )
combined p = the chance that a "chi-square" number (with 4 degrees of freedom) is at least X
```

- **ln** is the natural logarithm. It is the `ln` button on a calculator.
- If there are `k` p-values, the degrees of freedom are `2 × k`.
- If only the text p-value exists, the combined p-value is the text p-value.

**Our example:**

- **S2–S4:** `ln(0.0000000027) = −19.7` and `ln(4 × 10⁻⁹⁶) = −219.6`. So `X = −2 × (−19.7 − 219.6) ≈ 479`. The combined p-value is about **2 × 10⁻¹⁰²**.
- **S1–S3 (a normal pair):** text p = 0.12 and image p = 1. `X = −2 × (ln 0.12 + ln 1) = −2 × (−2.12 + 0) = 4.24`. The combined p-value is about **0.37**.

**What comes out:** one combined p-value for each pair.

**Why:** text and screenshots are separate kinds of evidence. Fisher's method is the standard way to join separate p-values into one.


### Method used here, and why

**Name: Fisher's combined probability test (with the chi-square distribution).**
*The formula:* `X = −2 × (ln(p_text) + ln(p_image))`, and the combined p-value is the chance that a chi-square number with `2 × k` degrees of freedom (4 for two p-values) is at least `X`.

**Why this formula:**

- When nothing is going on, a p-value is equally likely to be anywhere between 0 and 1. For such a number, `−2 × ln(p)` follows the chi-square distribution with 2 degrees of freedom.
- When you add `k` independent numbers of that kind, the sum follows the chi-square distribution with `2 × k` degrees of freedom. That is why the combined test uses `X` as a sum, and why 2 p-values give 4 degrees of freedom.
- A small p-value has a very negative `ln(p)`, so it makes `X` large. A large `X` has a small chance, so the combined p-value is small.
- **Why not just take the smaller p-value:** that would ignore the other evidence. Fisher's method gives a smaller combined p-value when **both** kinds of evidence agree, as in the example (0.01 and 0.05 together give about 0.004).
- **A short form for 4 degrees of freedom:** the chance that the chi-square number is at least `X` equals `e^(−X/2) × (1 + X/2)`. For S1–S3, `X = 4.24`, so the combined p-value is `e^(−2.12) × (1 + 2.12) = 0.12 × 3.12 = 0.37`.
- **Why a pair with no image has only the text p-value:** there is nothing to join.
- **Limit of this method:** it assumes that the text evidence and the image evidence are independent of each other. This is mostly reasonable, but it is not guaranteed.

---

## 15. Step 10: The q-value

**What goes in:** the combined p-values of **all** pairs.

**Why this step is needed:** the app tests many pairs. The more pairs it tests, the more likely it is that some pair gets a small p-value by luck. The q-value fixes this. The method is called **Benjamini–Hochberg**.

**What the app does:**

1. Sort the p-values from smallest to largest. The smallest has rank 1.
2. For each pair, work out: `p × n ÷ rank` (n = total number of pairs).
3. The **q-value** of a pair is the **smallest** of these numbers among its own rank and all the ranks above it. It is never more than 1.

**Our example** (n = 10 pairs):

| Rank | Pair | Combined p | p × 10 ÷ rank | q |
|---|---|---|---|---|
| 1 | S2–S4 | 2 × 10⁻¹⁰² | 2 × 10⁻¹⁰¹ | **2 × 10⁻¹⁰¹** |
| 2 | S1–S3 | 0.37 | 1.85 | 1 |
| 3 | S3–S5 | 0.52 | 1.73 | 1 |
| 4 to 10 | the other 7 pairs | 0.67 to 1.0 | 1.0 or more | 1 |

**What comes out:** `Q_Value` for each pair. The table is sorted with the smallest q-value first.

**What a q-value means:** if you call every pair with q below 0.01 suspicious, about 1 out of 100 of those pairs is expected to be a false alarm. This is only an estimate, because pairs that share a PDF are linked to each other. Use the q-value to **rank** the pairs.

**Why this method:** the old way (divide 0.05 by the number of pairs) is very strict and misses real cases when there are many pairs. Benjamini–Hochberg is made for finding the few pairs that stand out among many.


### Method used here, and why

**Name: Benjamini–Hochberg procedure (false discovery rate, FDR).**
*The formula:* `q = the smallest of (p × n ÷ rank)` over this pair's rank and all ranks above it, never more than 1.

**Why this formula, in detail:**

- Suppose nothing was going on. Then about `n × p` of the `n` pairs would have a p-value as small as `p` or smaller, just by luck. So `n × p` is the number of **false alarms expected** at that level.
- The `rank` of a pair is how many pairs *actually* have a p-value that small or smaller. That is the number of pairs that would be flagged at that level.
- So `n × p ÷ rank` = (false alarms expected) ÷ (pairs flagged). That is the estimated **share of false alarms among the flagged pairs**. This is the q-value.
- **Why "the smallest from this rank onwards":** a pair with a bigger p-value must never get a smaller q-value than a pair with a smaller p-value. Taking the smallest from this rank onwards keeps the order. It also means that, if a pair is flagged at some limit, every pair with a smaller p-value is flagged too.
- **Why not the strict method (`0.05 ÷ n`, called Bonferroni):** that method controls the chance of even *one* false alarm. With hundreds of pairs it becomes so strict that real copying is missed. Benjamini–Hochberg controls the **share** of false alarms among the flagged pairs, so a few real pairs can stand out among many. This is why it is used when many pairs are tested.
- **Limit of this method:** it works when the p-values are independent or tend to move together. Pairs that share a PDF are linked, so the q-value is an estimate. Use it to **rank** the pairs.

---

## 16. Step 11: The result

**What goes in:** the q-value, the longest run and the image result.

| Result | Rule |
|---|---|
| **Copied** | q is below **0.01** and the longest run is **10 words or more**. |
| **Needs review** | q is below **0.05** (and the result is not Copied). It is also used when the picture match is 0.92 or more and there were too few images for a test. |
| **No evidence** | None of the above. |

**The Evidence column (`Trigger_Type`):**

- **Text** = the text p-value is below 0.05.
- **Image** = the image p-value is below 0.05, or the fixed 0.92 rule applies.
- **Both** = both are true.

**A picture alone can never make a pair Copied.** Logos, textbook figures and shared templates can match without any copying. Copied always needs matching text.

**Our example:**

- **S2–S4:** q = 2 × 10⁻¹⁰¹, which is below 0.01 ✔. The longest run is 42 words, which is 10 or more ✔. The result is **Copied**. The text p-value (2.7 × 10⁻⁹) and the image p-value (4 × 10⁻⁹⁶) are both below 0.05, so the evidence is **Both**.
- **The other 9 pairs:** q = 1, which is not below 0.05. The result is **No evidence**.

**Constants and why:**

| Constant | Value | Why |
|---|---|---|
| `Q_COPIED` | 0.01 | A strict limit, so "Copied" is used only for strong cases. |
| `Q_REVIEW` | 0.05 | The usual 5% limit for "worth a look". |
| `MIN_RUN` | 10 words | A person can read a 10-word passage and judge it. Many short runs (for example many 5-word runs) can also give a small q-value. They show reworded text, so they get Needs review. This number is a rule of thumb. |


### Method used here, and why

**Name: significance limits (q below 0.01 and q below 0.05) together with a minimum-length rule (10 words).**

**Why the app does this:**

- A q-value limit says how unlikely the matching is by chance. **0.01** is strict, so "Copied" is only used for strong cases. **0.05** is the usual limit for "worth a look".
- **Why a second rule, a run of at least 10 words:** a small q-value says that the matching is not chance, but it does not say that a person can *see* the matching. A 10-word run is a passage that a person can read and judge. Many short runs (for example many 5-word runs) can also give a small q-value. That points to reworded text, so such a pair gets **Needs review** and not Copied.
- **Why a picture alone cannot give Copied:** logos, textbook figures and shared templates can match without anyone copying. Copied needs matching text.
- **Why 10 words:** it is a rule of thumb, not a calculated value.

---

## 17. Step 12: The reports

The app writes two CSV files. The table in the window shows the same rows.

**`pairwise_similarity_matrix.csv`** has one row for **every** pair.

| Column | Meaning |
|---|---|
| `PDF_1`, `PDF_2` | The two PDFs. |
| `Shared_Words` | Total words in all shared runs of 4 words or more. |
| `Longest_Match_Words` | Length of the longest shared run. |
| `Text_P_Value` | The text p-value from Step 6. (Empty if there are only 2 PDFs.) |
| `Image_Match_Percent` | The best screenshot match from Step 7. (Empty if there is none.) |
| `Q_Value` | The q-value from Step 10. (Empty if there are only 2 PDFs.) |
| `Trigger_Type` | Text, Image or Both. |
| `Verdict` | Copied, Needs review or No evidence. |

**Our example:** the first row of the file is:

| PDF_1 | PDF_2 | Shared_Words | Longest_Match_Words | Text_P_Value | Image_Match_Percent | Q_Value | Trigger_Type | Verdict |
|---|---|---|---|---|---|---|---|---|
| S2.pdf | S4.pdf | 57 | 42 | 2.7e-09 | 97.5 | 2e-101 | Both | Copied |

**`flagged_plagiarized_files.csv`** has only the pairs with the result **Copied**.

| Column | Meaning |
|---|---|
| `Flagged_PDF`, `Matched_With` | The two PDFs of the pair. |
| `Trigger_Type` | Text, Image or Both. |
| `Q_Value` | The q-value. |
| `Longest_Match_Words` | Length of the longest shared run. |
| `Shared_Passage` | The words of that longest run. |
| `Image_Match_Percent` | The best screenshot match. |
| `Faculty_Review_Status` | Empty. Fill in: Pending, Confirmed or Cleared. |
| `Teacher_Notes` | Empty. Write your own notes here. |

In our example this file has one row (S2 and S4), with the 42 words of the passage in `Shared_Passage`.

The app does **not** say who copied whom. It only says that the two PDFs match.

---

## 18. What happens with only 2 PDFs

With only 2 PDFs there are no other pairs to learn from. So Steps 5 to 10 cannot be done. There is **no p-value and no q-value**. The app uses these simple rules:

- Longest run of **10 words or more** gives **Needs review**.
- Picture match of **0.92 or more** gives **Needs review**.
- **Both** give **Copied**.

Text that both students copied from the question looks like copying here. So give the app the **prompt file** when you check 2 PDFs.

With **3 to 5 PDFs** the app works, but it shows a warning: "normal" is learned from only a few pairs, so the numbers are rough. Ten or more PDFs is better.

---

## 19. All the constants in one table

They are at the top of `engine.py`. Changing them changes how strict the app is.

| Constant | Value | Step | Why this value |
|---|---|---|---|
| `SHINGLE` | 3 words | 3, 4 | One word is shared by all documents. Three words in the same order are rarely shared by chance. |
| `MIN_RUN` | 10 words | 11 | A passage a person can read and judge. A rule of thumb. |
| `MIN_TEST_WORDS` | 4 words | 6 | Runs of 3 words happen by chance too often. |
| `Q_COPIED` | 0.01 | 11 | Strict limit for "Copied". |
| `Q_REVIEW` | 0.05 | 6, 8, 11 | The usual limit for "worth a look". |
| `EMP_MAX` | 14 words | 5 | The longest length where chance runs can usually be counted. |
| `DEFAULT_DECAY` | 0.3 | 5 | Used only when the decay cannot be measured. |
| `DECAY_RANGE` | 0.05 to 0.7 | 5 | Keeps the decay sensible. |
| `IMG_MATCH` | 0.92 | 8, 11 | Fixed rule when there are too few images for a test. |
| `IMG_MIN` | 0.75 | 8 | A weak match is never called suspicious. |
| `IMG_TOL` | 30 grey levels | 7 | Allows for resizing and JPEG changes. |
| `IMG_SIZE` | 512 × 320 | 1, 7 | One common size for comparing pixels. |
| `MIN_MASK` | 0.003 (0.3%) | 7 | Skips pictures with almost no content of their own. |
| `MIN_IMG_PX` | 80 pixels | 1 | Ignores icons and bullets. |
| `MARGIN` | 0.07 (7%) | 1 | Ignores headers, footers and page numbers. |
| Rare-phrase formula | 15% and 3 | 3 | A phrase in more than about 15% of PDFs is normal wording. The 3 keeps small copying groups visible. |
| Other numbers in the code | 2,500 · 0.05 · 1.4826 · 0.03 · 8 | 4, 7, 8 | 2,500 = repetition limit. 0.05 = shape step. 1.4826 = changes MAD into the usual spread. 0.03 = smallest spread. 8 = fewest image matches for a test. |

---

## 20. What the app cannot do

- **It was tested only on made-up sample text.** The constants may need changing for your classes.
- **It misses reworded or translated copying.** Many short matching runs can give Needs review, but a fully rewritten text will not match.
- **It cannot read text inside pictures, and it cannot read scanned PDFs.** The app has no text recognition. A scanned page gives no text to compare.
- **It only compares pictures that are stored in the PDF.** Charts drawn as shapes are not compared.
- **It needs the same picture.** A screenshot that was cropped, moved, resized or taken again will not match.
- **It cannot tell copying from a shared source.** Students who quote the same book, use the same lab manual or the same given code can match.
- **It learns "normal" from the folder.** If the folder holds different assignments, or only a few PDFs, the numbers are less reliable.
- **A small q-value is a strong signal, not an exact probability.** Phrases in real text are not perfectly independent. Use q-values to rank pairs.
- **It does not say who copied whom.**

Always open both PDFs and read the shared passage before you decide anything.

---

## 21. Files in this project

| File | What it holds |
|---|---|
| `app.py` | The window: folders, progress bar, table and detail view. |
| `engine.py` | All 12 steps in this file. |
| `requirements.txt` | The libraries to install. |
| `README.md` | This file. |