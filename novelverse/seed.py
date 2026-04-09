"""Seed the database with demo data for NovelVerse."""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from database import DATABASE, init_db
from utils.auth import hash_password

def seed():
    init_db()
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row

    # ── Users ──────────────────────────────────────────────────────────────────
    users = [
        ('admin',    'admin@novelverse.com',    'password123', 1, 1, 'Site administrator and avid reader.'),
        ('Elara',    'elara@example.com',        'password123', 1, 0, 'Writes epic fantasy and cultivation stories. Coffee addict.'),
        ('Thorin',   'thorin@example.com',       'password123', 1, 0, 'LitRPG enthusiast. Currently writing my third series.'),
        ('Mira',     'mira@example.com',         'password123', 1, 0, 'Romance and slice-of-life author. Believes in happy endings.'),
        ('reader1',  'reader1@example.com',      'password123', 0, 0, 'Just here for the stories.'),
        ('reader2',  'reader2@example.com',      'password123', 0, 0, 'Fantasy and sci-fi fanatic.'),
    ]
    user_ids = {}
    for username, email, pw, is_author, is_admin, bio in users:
        existing = db.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()
        if existing:
            user_ids[username] = existing['id']
            continue
        pw_hash, salt = hash_password(pw)
        db.execute('INSERT INTO users(username,email,password_hash,salt,is_author,is_admin,bio) VALUES(?,?,?,?,?,?,?)',
                   (username,email,pw_hash,salt,is_author,is_admin,bio))
        user_ids[username] = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # ── Novels ────────────────────────────────────────────────────────────────
    novels_data = [
        ('Elara', 'The Shattered Throne', 'Fantasy',
         'When the last king falls, a forgotten heir must rise — or watch the realm crumble to ash. Lyra never wanted the crown. But fate rarely asks permission.',
         'ongoing', 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
         ['epic-fantasy','political-intrigue','chosen-one','slow-burn','magic-system']),
        ('Elara', 'Roots of the Eternal Sky', 'Cultivation',
         'Born without a spiritual root, Wei Chen must cultivate through unconventional means to reach the heavens. A classic xianxia tale with a modern twist.',
         'ongoing', '',
         ['cultivation','xianxia','underdog-mc','progression','martial-arts']),
        ('Thorin', 'System Override', 'LitRPG',
         '[You have been selected as a Beta Tester for Earth\'s Integration into the Greater Cosmos.] Jake was just a programmer. Now he has to become something much more.',
         'ongoing', 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=400&h=600&fit=crop',
         ['litrpg','system','overpowered-mc','action','gamelit']),
        ('Thorin', 'The Final Dungeon', 'Fantasy',
         'A veteran adventurer takes on one last quest: clear the dungeon that has never been completed in a thousand years. What awaits at the final floor?',
         'completed', '',
         ['dungeon','adventurer','completed','action','mystery']),
        ('Mira', 'Coffee and Catastrophes', 'Romance',
         'Nora runs the only cafe in a small town that never sleeps. When a brooding novelist takes the corner table every morning, things get complicated — and delicious.',
         'ongoing', 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400&h=600&fit=crop',
         ['romance','slice-of-life','coffee-shop','enemies-to-lovers','cozy']),
    ]
    novel_ids = {}
    for author, title, genre, desc, status, cover, tags in novels_data:
        existing = db.execute('SELECT id FROM novels WHERE title=?',(title,)).fetchone()
        if existing:
            novel_ids[title] = existing['id']
            continue
        db.execute('INSERT INTO novels(author_id,title,description,genre,status,cover_url) VALUES(?,?,?,?,?,?)',
                   (user_ids[author],title,desc,genre,status,cover))
        nid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        novel_ids[title] = nid
        for tag in tags:
            db.execute('INSERT INTO novel_tags(novel_id,tag) VALUES(?,?)',(nid,tag))

    # ── Chapters ──────────────────────────────────────────────────────────────
    chapters_by_novel = {
        'The Shattered Throne': [
            ('Prologue: The Last King', '''The throne room smelled of smoke and betrayal.

King Aldric sat slumped against the obsidian throne, the golden crown tilted on his grey head, blood seeping through the cracks in his ceremonial armor. The candles had burned to stubs. Outside, the capital city of Vaelmore screamed.

Lyra pressed herself against the cold stone column, watching. She had come to plead for her village's taxes. Instead, she witnessed the end of an age.

"Find the heir," the king rasped to no one. His eyes, milky with age, found hers across the vast hall — and she knew he could not possibly see her. Yet he pointed.

Directly at her.

"The realm remembers," he whispered. Then he was still.

Lyra's hand went to the mark on her wrist she had always hidden. The silver crescent, the color of a dead moon, began to glow.

She ran.'''),
            ('Chapter 1: The Unwanted Gift', '''Three days after the king died, the armies came.

Lyra had made it back to Ashford — a village so small and unremarkable that it barely appeared on kingdom maps. She'd thought that anonymity would protect her. She'd been wrong.

The soldiers wore the black-and-silver of House Morrath, the king's cousins who had been angling for succession for twenty years. They came in the predawn grey, when honest people were still asleep and only the roosters and the guilty were awake.

Lyra was both.

"Girl," said the captain at her door. He was a large man with small eyes. "You'll want to come quietly."

Behind her, she heard her grandmother shuffle from the back room. The old woman had known. Lyra realized this with a lurch — had known and never told her.

"Gran—"

"I never had a granddaughter," the woman said, and her voice was perfectly steady. "I had a ward."

The mark on Lyra's wrist burned like ice.'''),
            ('Chapter 2: The Road to Nowhere Good', '''The prisoner wagon was not made for comfort.

Lyra shared it with a pickpocket named Davan who talked too much and a former court mage who said nothing at all. The mage was perhaps fifty, with close-cropped silver hair and eyes the color of deep water. She had been studying Lyra since they departed.

"You don't know what you are," the mage said on the second day. It was not a question.

"I know exactly what I am," Lyra said. "A tax collector's apprentice who had very bad timing."

"You have the Wanderer's Mark." The mage nodded at Lyra's wrist. "The last person to carry it led the Second Restoration four hundred years ago. Before that, she burned half the continent."

Davan stopped his nervous fidgeting. The wagon wheels groaned.

"I'm not burning anything," Lyra said.

"No," the mage agreed, tilting her head. "You'll do something far more interesting." She paused. "My name is Seren. I suggest we become friends before we reach the capital. You will need someone who knows its shadows."'''),
        ],
        'System Override': [
            ('Chapter 1: [Beta Tester Selected]', '''Jake was debugging a memory leak at 2am when the notification appeared.

Not on his monitor. Not on his phone. In the air in front of him, rendered in crisp blue light that cast no shadows.

[SYSTEM NOTIFICATION]
Congratulations, Jake Harmon. You have been selected as one of ten thousand Beta Testers for Earth's Integration into the Greater Cosmos Network. Your participation is mandatory.

Integration begins in: 00:00:05

"What the—"

00:00:04

Jake stood up so fast his chair rolled back and hit the wall.

00:00:03

He tried to dismiss the window. His hand passed through it.

00:00:02

"Okay," he said, to no one, to the universe, to whatever was about to change his life. "Okay."

00:00:01

A sound like every bell ever rung at once.

And then the world cracked open, and something vast looked in.

[Welcome to the Integration Protocol, Beta Tester #7,441]
[Scanning biological substrate... Complete]
[Assigning Class... Processing...]
[Unusual compatibility detected. Stand by.]'''),
            ('Chapter 2: A Terrible, Wonderful Class', '''[Class Assignment: ARCHITECT OF SYSTEMS — Tier 0 (Unranked)]
[This class has not been seen in the Greater Cosmos Network in 3,200 years.]
[Warning: This class has a 94.7% mortality rate in the first Integration year.]
[Additional Warning: The remaining 5.3% went on to become Cosmos-ranked individuals.]
[Good luck.]

Jake read the floating text three times.

Around him, his apartment was exactly as it had been. His coffee mug still steamed. The memory leak was probably still leaking. Outside, a car alarm went off with complete indifference to the fundamental restructuring of reality.

He pulled up the full System interface with a thought — that part was new, the thinking-and-it-happens — and started reading.

ARCHITECT OF SYSTEMS
A class that does not cast spells. It writes the rules that govern them.
Starting Abilities: [Analyze] [Deconstruct] [Rewrite (Limited)]
Starting Stats: INT 24, WIS 18, STR 4, AGI 6, CON 7

The stats were... mixed. The INT was absurd for a starting class. The STR was embarrassing.

"Rewrite," he said out loud, experimentally.

[Rewrite (Limited): Select a System rule within your tier and modify one parameter. Cooldown: 24 hours. Warning: Changes are permanent and affect all entities under that rule.]

Jake sat back down in his chair.

He was going to need more coffee. And possibly a therapist. But mostly more coffee.'''),
        ],
        'Coffee and Catastrophes': [
            ('Chapter 1: The Corner Table', '''The first thing Nora noticed about him was that he ordered black coffee and looked personally offended by the sound of the milk frother.

The second thing was that he brought a typewriter.

An actual, physical, clacking-and-dinging typewriter, which he set on the corner table — her corner table, the one she kept clear with a small "Reserved" sign that everyone in Millhaven knew was just for decoration — and proceeded to type at with the focused aggression of someone at war with language itself.

"You can't use that in here," Nora said.

He looked up. He had dark circles under darker eyes and the expression of a man who had been awake for thirty hours and resented the world for requiring sleep.

"The sign outside says 'Writers Welcome,'" he said.

"That sign is forty years old and refers to people who write in notebooks like normal humans."

"I write on a typewriter."

"I see that."

"Then we're in agreement." He looked back down and typed three aggressive sentences.

Nora stood at the counter for a long moment.

The cafe was otherwise empty. It was 6:47am on a Tuesday in November, and the town of Millhaven had not yet decided to be awake.

She poured a second black coffee — which she had not been asked for — walked to the corner table, and set it down next to the typewriter.

He didn't thank her. But she noticed he drank it.'''),
            ('Chapter 2: Bad at Names, Good at Coffee', '''His name, she found out two weeks later, was Callum. 

She found this out not because he introduced himself but because the package that arrived addressed to "C. Reyes, Millhaven Bed & Breakfast" was delivered to the cafe by mistake, and she read the label before she thought better of it.

"Callum Reyes," she said when she brought it over. "I always wondered."

He looked up with the expression he usually saved for adverbs. "You know my name."

"Package." She set it on the table. "It was misdelivered."

He looked at the package, then at her. Something shifted in his expression — not warmth exactly, more like the door to a room with warmth in it had opened slightly.

"Nora," he said.

"You read my name tag."

"You read my mail."

"Fair point." She turned to go.

"The coffee here is good," he said. Which from someone who delivered every compliment like a reluctant confession was, she understood, significant.

She didn't smile until she was back behind the counter.

"You're smiling," said her barista, Marcus, with the delight of someone who had been waiting for exactly this.

"I'm not," said Nora.

"You absolutely are."

She poured a coffee and pretended very hard that he was wrong.'''),
        ],
    }

    for novel_title, chaps in chapters_by_novel.items():
        nid = novel_ids.get(novel_title)
        if not nid: continue
        for i, (title, content) in enumerate(chaps, 1):
            existing = db.execute('SELECT id FROM chapters WHERE novel_id=? AND chapter_number=?',(nid,i)).fetchone()
            if not existing:
                db.execute('INSERT INTO chapters(novel_id,chapter_number,title,content,published,views) VALUES(?,?,?,?,1,?)',
                           (nid,i,title,content,50+i*23+nid*7))

    # ── Reviews ───────────────────────────────────────────────────────────────
    reviews = [
        ('reader1','The Shattered Throne',5,'Absolutely gripping from the first paragraph. The worldbuilding is subtle but rich, and Lyra is one of the best protagonists I\'ve read in years.'),
        ('reader2','The Shattered Throne',4,'Great prose and characters. The pacing in chapter 2 slows slightly but the payoff is worth it.'),
        ('reader1','System Override',5,'I\'ve read a lot of LitRPG and this one stands apart. The system feels genuinely clever, not just window dressing.'),
        ('reader2','Coffee and Catastrophes',5,'I did not expect to feel this much about a man with a typewriter. Beautiful slow burn.'),
        ('reader1','Coffee and Catastrophes',4,'Cozy, funny, and the coffee descriptions make me want to open a cafe myself.'),
    ]
    for username, novel_title, rating, body in reviews:
        uid = user_ids.get(username)
        nid = novel_ids.get(novel_title)
        if uid and nid:
            existing = db.execute('SELECT id FROM reviews WHERE novel_id=? AND user_id=?',(nid,uid)).fetchone()
            if not existing:
                db.execute('INSERT INTO reviews(novel_id,user_id,rating,body) VALUES(?,?,?,?)',(nid,uid,rating,body))

    # ── Follows ───────────────────────────────────────────────────────────────
    follows = [
        ('reader1','The Shattered Throne'),
        ('reader1','System Override'),
        ('reader2','The Shattered Throne'),
        ('reader2','Coffee and Catastrophes'),
        ('reader1','Coffee and Catastrophes'),
        ('Thorin','The Shattered Throne'),
        ('Mira','System Override'),
        ('Elara','Coffee and Catastrophes'),
    ]
    for username, novel_title in follows:
        uid = user_ids.get(username)
        nid = novel_ids.get(novel_title)
        if uid and nid:
            existing = db.execute('SELECT 1 FROM novel_follows WHERE novel_id=? AND user_id=?',(nid,uid)).fetchone()
            if not existing:
                db.execute('INSERT INTO novel_follows(novel_id,user_id) VALUES(?,?)',(nid,uid))

    # ── Views ─────────────────────────────────────────────────────────────────
    import random
    random.seed(42)
    for nid in novel_ids.values():
        for _ in range(random.randint(30, 80)):
            days_ago = random.randint(0,29)
            db.execute(f"INSERT INTO novel_views(novel_id,ip_address,viewed_at) VALUES(?,?, datetime('now', '-{days_ago} days'))",
                       (nid, f'192.168.{random.randint(1,255)}.{random.randint(1,255)}'))

    # ── Comments ──────────────────────────────────────────────────────────────
    comments = [
        ('reader1','The Shattered Throne',None,"The opening line of the prologue hit me like a freight train. Instant follow."),
        ('reader2','The Shattered Throne',None,"Seren is my favorite character already. Please write more of her."),
        ('reader1','System Override',None,"'Architect of Systems' is such a creative class concept. The 94.7% mortality rate detail cracked me up."),
        ('reader2','Coffee and Catastrophes',None,"I am the corner table man. This story is about me specifically."),
    ]
    for username, novel_title, chapter_id, body in comments:
        uid = user_ids.get(username)
        nid = novel_ids.get(novel_title)
        if uid and nid:
            existing = db.execute('SELECT 1 FROM comments WHERE user_id=? AND novel_id=? AND body=?',(uid,nid,body)).fetchone()
            if not existing:
                db.execute('INSERT INTO comments(user_id,novel_id,chapter_id,body) VALUES(?,?,?,?)',(uid,nid,chapter_id,body))

    db.commit()
    db.close()
    print("✓ Database seeded successfully!")
    print("\nDemo accounts (password: password123):")
    print("  admin   — admin account")
    print("  Elara   — author (fantasy/cultivation novels)")
    print("  Thorin  — author (LitRPG novels)")
    print("  Mira    — author (romance novels)")
    print("  reader1 — reader account")
    print("  reader2 — reader account")

if __name__ == '__main__':
    seed()
