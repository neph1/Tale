This fork uses an LLM backend to describe things in a more vivid way. (LLM not included)

By default it uses KoboldCpp, but if you're feeling adventurous you can change llm_config.yaml in the tale/ folder to another one. 

2. Get and install KoboldCpp: https://github.com/LostRuins/koboldcpp/releases
3. Download a suitable llm model for koboldcpp. I recommend https://huggingface.co/TheBloke/Nous-Hermes-Llama2-GGML or https://huggingface.co/TheBloke/chronos-hermes-13B-GGML
4. Make sure KoboldCpp works.
1. Download repo, either with 'git clone' or as a zip.
6. Run 'pip install -r requirements.txt'
7. Start KoboldCpp (port 5001 by default)
8. Start with ``python -m stories.prancingllama.story``

In the game:
You can probably read up on this, or use 'help' in the prompt, but you can move around using directions, like n, w, s, e, or type the location you want to go to.
To trigger a dialogue, address people with 'say character: what you want to say'. There are a number of 'aliases' for each character, and the game seems to help you find the right one.

Features:
* When the MUD describes something, through commands like 'look' or other verbs, it sends the original description as a prompt to the LLM. The LLM either has free hands to write as much as it wants, or for some things, it's limited to a certain amount of tokens, not to cause too many delays.
* Not only for player-driven actions, mobs and NPC's also trigger this.
* It has a 'rolling memory' of previous generations, this is inserted before the instructions in the prompt with each request. This should help it keep the context.
* Characters have a short memory for conversations to keep them on track, as well.

Caveats:
* Like any LLM generated content, it's only as good as its input, and can sometimes go off-track when generating responses. Thus, the original description the MUD generates is also included, not to lose any important data.
* The LLM (currently) can't drive any actions. There's no parsing happening of the content it generates.
* It's written specifically for KoboldCpp as backend, but as much as possible of the config is in llm_config.yaml, so you can experiment with other backends as well.



Example:

Here's the kind of output you can except. "Original" is the written description. "Generated" is what the LLM produces.

Scenario background story: After a grizzling journey through the snow storm you have finally
  arrived at  The Prancing Llama, the only refuge for miles and miles in
  this craggy, snow-covered landscape.  You have heard many tales about
  this place, but now the time has come to make your own.
  
>  Original:[ [’[Entrance]’, ’A room full of furry and snow-covered
  coats.  Loud voices and roars of laughter can be heard from the main
  hall.’, “There’s a warm glow and loud, noisy conversations coming
  through a doorway to the north “] ] Generated: As I entered the
  building, I was greeted by a sea of fluffy and snow-dusted jackets,
  their colors and patterns as varied as the people wearing them.  The
  air was alive with excited chatter and boisterous laughter, echoing
  off the walls like a symphony of joy.  To my left, a door stood open,
  revealing a room ablaze in light and sound - voices mingling together
  in a cacophony of warmth and camaraderie.

> Original:[ [’[Main Hall]’, ’An area full of tables with people eating,
  drinking and talking’, ’  To the west you see a giant hearth with a
  comforting fire’, ’A fierce looking woman sitting by a table, whose
  eyes seem to follow you.  A slender gentleman with a patch over one of
  his eyes, leaning against the wall.’] ] Generated: As I entered the
  building, my gaze was immediately drawn to the bustling main hall,
  where tables were scattered throughout the room like islands in a sea
  of chatter and laughter.  The air was thick with the scent of
  delicious food and warmth, and my stomach rumbled in anticipation.  By
  the west wall, a massive hearth roared with life, its flames casting
  flickering shadows across the room as they danced on the walls.  In
  one corner, a fierce-looking woman sat at her table, her eyes
  constantly moving as she surveyed the scene around her.  Next to her,
  a slender gentleman with a patch over one eye leaned against the wall,
  his gaze fixed on something beyond my line of sight.I couldn’t
  help but feel a sense of excitement as I made my way towards them,
  eager to join in the merriment and warmth that filled the room.


Excerpt from talking to Elid (prompting with his ‘character card’):

 
  You say: elid: ’what are you doing here?’.

>   Elid Gald says: “Elid Gald chuckles mischievously at Arto’s question
  and smirks, adjusting his hat before responding, “Why, I’m just
  enjoying a stroll through the market, my dear sir.  And what about
  yourself?  What brings you to these parts?”  His voice is smooth and
  alluring with an undercurrent of danger hidden beneath it.”

  You say: elid: ’i’m looking for some goods to buy, my purse is laden
  with gold’.

>   Elid Gald says: “Elid Gald nods approvingly at Arto’s mention of
  wealth and grins wickedly, leaning in closer to whisper, “Well then,
  perhaps I can help you find something truly unique and valuable.
  Perhaps some items that are not available on the open market, eh?  You
  see, I have connections with certain…merchants who might be willing
  to part with their finest wares for someone like you.”  He pauses
  meaningfully, allowing the implication to linger in the air between
  them as his hand slips casually into his pocket.As he speaks, one
  could almost hear the clinking of coins in his pocket - but whether
  it’s real or just a clever illusion is anyone’s guess.  “You know,” he
  says softly, “I’ve always been known for my eye for rare and exquisite
  goods.  Why not let me help you acquire something truly special?
  After all, I’m sure you don’t want to be caught with common trinkets.”
  His voice is silky smooth and seductive as he leans even closer to
  Arto, a glint of mischief in his remaining eye.”Wouldn’t you
  rather have something that sets you apart from others?  Something that
  screams ’wealthy aristocrat’?””

You say: elid: ’maybe you’re right.. do you charge a fee for your
  services?’.

>   Elid Gald says: “Elid Gald chuckles softly and takes a step back,
  giving Arto an appraising look.  “I always charge a fee, young man,”
  he says with a smirk, “And my fee is quite substantial.  But I believe
  that the items I can help you acquire will be more than worth it.”
  His voice is still silky smooth and seductive, his mischievous gaze
  never leaving Arto’s face.\n”However,” He continues, “If you’re
  willing to make a deal with me… let’s say, a mutually beneficial
  agreement… then we could discuss a different kind of payment.”  He
  winks at Arto, his remaining eye gleaming with curiosity.”What do
  you think?  Are you willing to take a risk for something truly
  unique?””






ORIGINAL README for Tale (public archive):


----------------------



[![saythanks](https://img.shields.io/badge/say-thanks-ff69b4.svg)](https://saythanks.io/to/irmen)
[![Build Status](https://travis-ci.org/irmen/Tale.svg?branch=master)](https://travis-ci.org/irmen/Tale)
[![Latest Version](https://img.shields.io/pypi/v/tale.svg)](https://pypi.python.org/pypi/tale/)

![Tale logo](docs/source/_static/tale-large.png)

'Tale' - mud, mudlib & interactive fiction framework [frozen]
=============================================================

This software is copyright (c) by Irmen de Jong (irmen@razorvine.net).

This software is released under the GNU LGPL v3 software license.
This license, including disclaimer, is available in the 'LICENSE.txt' file.



Tale requires Python 3.5 or newer.
(If you have an older version of Python, stick to Tale 2.8 or older, which still supports Python 2.7 as well)

Required third party libraries:
- ``appdirs`` (to load and save games and config data in the correct folder).
- ``colorama`` (for stylized console output)
- ``serpent`` (to be able to create save game data from the game world)
- ``smartypants`` (for nicely quoted string output)
 
Optional third party library:
- ``prompt_toolkit``  (provides a nicer console text interface experience)

Read the documentation for more details on how to get started, see http://tale.readthedocs.io/

EXAMPLE STORIES
---------------

There is a trivial example built into tale, you can start it when you have the library installed
by simply typing:  ``python -m tale.demo.story``
 
On github and in the source distribution there are several much larger [example stories](stories/) and MUD examples.
* 'circle' - MUD that interprets CircleMud's data files and builds the world from those
* 'demo' - a random collection of stuff including a shop with some people
* 'zed_is_me' - a small single player (interactive fiction) survival adventure
