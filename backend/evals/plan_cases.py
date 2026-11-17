"""
Plans typed in plain words, with the answer a person would expect, to score
how well each reader (built-in, Ollama, Claude) fills in Start Session.

Each case is (now, text, place, back_by):

- now: the phone's local time on Tuesday 2026-10-27 in New York, "HH:MM".
- place: the destination expected, None if the plan names no place, or "*"
  when any answer is fine (e.g. "visiting mom").
- back_by: "HH:MM" today, "+HH:MM" tomorrow, None when the app should ask
  for a time instead (no time given, too soon, too far, not a real time),
  or a tuple of two times when the app should ask "AM or PM?".

Run: python scripts/score_plans.py --reader basic|ollama|claude
"""

CASES: list[tuple[str, str, str | None, str | tuple[str, str] | None]] = [
    # ----- Evening, 6:05 PM -----
    ("18:05", "Dinner at Olive Garden on Main St, back by 11", "Olive Garden on Main St", "23:00"),
    ("18:05", "Heading to the gym, home by 7:30pm", "gym", "19:30"),
    ("18:05", "Walking to Sam's house until 9", "Sam's house", "21:00"),
    ("18:05", "Drinks at The Anchor for 2 hours", "The Anchor", "20:05"),
    ("18:05", "Movie at AMC, back at midnight", "AMC", "+00:00"),
    ("18:05", "Hiking at Bear Mountain, back by 8am tomorrow", "Bear Mountain", "+08:00"),
    ("18:05", "Going to the library", "library", None),
    ("18:05", "dinner w/ Sam @ olive garden, home ~quarter to 11", "olive garden", "22:45"),
    ("18:05", "Bar crawl downtown, home by 1:30am", "*", "+01:30"),
    ("18:05", "Movie at AMC for 2 hours then 20 min drive home", "AMC", "20:25"),
    ("18:05", "Party at Jess's place, back around 1", "Jess's place", "+01:00"),
    ("18:05", "Concert at Madison Square Garden, back by 12", "Madison Square Garden", "+00:00"),
    ("18:05", "Run in the park for 45 min", "park", "18:50"),
    ("18:05", "Out with friends for a couple of hours", "*", "20:05"),
    ("18:05", "Grabbing groceries at Trader Joe's, back in half an hour", "Trader Joe's", "18:35"),
    ("18:05", "Date night at Lucali, home by 10ish", "Lucali", "22:00"),
    ("18:05", "Late shift at work, back at 2:30 am", "work", "+02:30"),
    ("18:05", "Visiting mom, back by 9 tonight", "*", "21:00"),
    ("18:05", "Walking the dog for 20 minutes", "*", "18:25"),
    ("18:05", "Pickup basketball at the Y for an hour and a half", "Y", "19:35"),
    ("18:05", "back in 2 min", None, None),
    ("18:05", "Road trip, back in 30 hours", "*", None),
    ("18:05", "Dinner then movie, home by 11:30", "*", "23:30"),
    ("18:05", "Study group at the library until half past 9", "library", "21:30"),
    ("18:05", "Bowling at Lucky Strike, back at 9:45 pm", "Lucky Strike", "21:45"),
    (
        "18:05",
        "meeting a date at starbucks on 5th ave, back in 2 hrs",
        "starbucks on 5th ave",
        "20:05",
    ),
    ("18:05", "Going to Brooklyn for 2-3 hours", "Brooklyn", "21:05"),
    ("18:05", "Uber to JFK, back tomorrow 6pm", "JFK", "+18:00"),
    (
        "18:05",
        "I'll be at Joe's Pizza on Bleecker St, back by 10 pm",
        "Joe's Pizza on Bleecker St",
        "22:00",
    ),
    ("18:05", "gng to gym bk by 8", "gym", "20:00"),
    ("18:05", "headed to sams, home 2nite at 11", "sams", "23:00"),
    ("18:05", "Back by 9:75", None, None),
    # ----- Morning, 10:30 AM -----
    ("10:30", "Coffee at Blue Bottle, back by 11", "Blue Bottle", ("11:00", "23:00")),
    ("10:30", "Brunch at Sarabeth's, back by 1", "Sarabeth's", "13:00"),
    ("10:30", "Doctor appointment, back by 12:30", "*", "12:30"),
    ("10:30", "Jog in Central Park, back at 11:15", "Central Park", ("11:15", "23:15")),
    ("10:30", "Errands, back around noon", "*", "12:00"),
    ("10:30", "Breakfast at the diner, back by 11:30", "diner", "11:30"),
    (
        "10:30",
        "Lunch at Olive Garden for an hour and be back in 30 minutes after lunch.",
        "Olive Garden",
        "12:00",
    ),
    ("10:30", "Taking the kids to the zoo, home by 4", "zoo", "16:00"),
    ("10:30", "Work at the office, back at 6", "office", "18:00"),
    ("10:30", "Picnic at Prospect Park till 3pm", "Prospect Park", "15:00"),
    ("10:30", "Shopping at the mall for a few hours", "mall", "13:30"),
    ("10:30", "showup at store and be back by 11.30", "store", ("11:30", "23:30")),
    ("10:30", "Gym for 1.5 hours", "*", "12:00"),
    ("10:30", "Dinner at Nobu, home by 10.15", "Nobu", "22:15"),
    # ----- Night, 11:30 PM -----
    ("23:30", "Walking home from the bar, 20 min", "*", "23:50"),
    ("23:30", "Club in the Meatpacking district, back by 3", "*", "+03:00"),
    ("23:30", "Night shift at the hospital, home by 7am", "hospital", "+07:00"),
    ("23:30", "Out, back by 1", "*", "+01:00"),
    ("23:30", "Late movie at AMC, home by 2", "AMC", "+02:00"),
    # ----- Afternoon, 2:00 PM -----
    ("14:00", "Soccer practice at Riverside Park, back by 5:30", "Riverside Park", "17:30"),
    ("14:00", "Dentist on Main St, back in 90 minutes", "*", "15:30"),
    ("14:00", "Coffee with Priya at Blue Bottle, back around 3:30", "Blue Bottle", "15:30"),
    ("14:00", "Hair appointment, home by 4", "*", "16:00"),
    ("14:00", "Volunteering at the food bank for 3 hours", "food bank", "17:00"),
    ("14:00", "Hanging out at Mike's, back in an hour or two", "Mike's", "16:00"),
    ("14:00", "visiting grandma tomorrow, back by 9", "*", "+09:00"),
    ("14:00", "beach w the girls til 6", "*", "18:00"),
    ("14:00", "Getting a haircut, 45 mins", "*", "14:45"),
    ("14:00", "Walk around the block", "*", None),
    ("14:00", "Library till closing", "*", None),
]
