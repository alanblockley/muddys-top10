# Muddy's Top 10 - Listener Guide

Welcome to **Muddy's Top 10** - your real-time chart of the hottest tracks playing on Muddy's Music Cafe!

## What is Muddy's Top 10?

The **Muddy's Top 10** is a weekly chart that showcases the most played tracks on Muddy's Music Cafe radio station. Unlike other music charts based on streaming numbers or sales, our Top 10 reflects what's actually spinning in the DJ booth and what listeners are requesting.

**This is YOUR chart** - built from real DJ playout decisions and customer requests throughout the week.

## How It Works

### 🎧 Real DJ Plays, Real Chart
Every track played on Muddy's Music Cafe is automatically logged in real-time. Our system monitors the radio stream 24/7, capturing every song the DJs play and every request they fulfill.

### 📊 Weekly Rankings
Each week, we count up which tracks were played the most:
- **Monday to Sunday** - One full week of airplay
- **Every play counts** - Whether it's a DJ favorite or a listener request
- **Fresh every week** - Charts reset Monday, so new favorites can rise fast

### 🎵 What Gets Counted?
- Songs played by our DJs
- Customer requests honored by the DJs
- Regular rotation tracks
- Special event plays

### ⛔ What Doesn't Count?
- Station IDs and promotional announcements
- DJ talk segments
- Advertising messages
- Technical test tracks

## Reading the Chart

### The Top 10 Display

When you visit the Top 10 page, you'll see the current week's hottest tracks with some cool indicators:

**Rank Badge** - Shows the track's current position (#1 through #10)

**Movement Indicators:**
- **🔥 NEW** - Brand new entry to the Top 10 this week
- **⬆️ UP** - Moved up from last week (shows how many spots)
- **⬇️ DOWN** - Moved down from last week (shows how many spots)
- **➡️ SAME** - Holding steady at the same position
- **🔄 RE-ENTRY** - Was in the Top 10 before, dropped out, now back!

**Play Count** - How many times the track was played this week

**Previous Rank** - Where it was last week (if it was in the Top 10)

### Example
```
#1  🔥 NEW
Artist Name - Track Title
45 plays this week
```
This track is brand new to the Top 10 and already hit #1 with 45 plays!

```
#3  ⬆️ UP +2
Artist Name - Track Title
38 plays this week | Previously #5
```
This track jumped from #5 to #3 - clearly gaining momentum!

## Why Your Requests Matter

When you call in or message a request to the DJ, and they play it, that track gets logged. If enough listeners are requesting the same track, it climbs the chart.

**Want to see your favorite track hit #1?**
- Request it when you tune in
- Encourage friends to request it too
- The more it gets played, the higher it climbs!

## Chart Week

- **Starts:** Monday 12:00 AM PST
- **Ends:** Sunday 11:59 PM PST
- **Updates:** Live! The chart updates throughout the week
- **New Rankings:** Posted every Monday morning

## View the History

Want to know what was playing on a specific day? The **History View** (available through the admin panel) shows every track played, organized in 2-hour blocks. This feature is perfect for:
- Finding out what song was playing during your favorite moment
- Checking out a specific DJ's playlist
- Seeing how busy different times of day are

## Track Validation

You might notice some track names look a bit different from what the DJ announced. Our system automatically validates and corrects track information using music databases to ensure:
- **Accurate artist names** - No more "HUNTRIX" when it's actually "HUNTR/X"
- **Proper capitalization** - Consistent formatting across all entries
- **Typo correction** - Catches common misspellings
- **Clean formatting** - Removes DJ pool tags and technical markers

This means the chart shows the **canonical** (official) track names, making it easier to find the songs on streaming platforms or in record stores.

## Technical Details (For the Curious)

Our system runs on AWS cloud infrastructure, monitoring the Muddy's Music Cafe stream every minute. When a new track starts playing:

1. **Detection** - System picks up the track metadata from the stream
2. **Cleaning** - Removes technical markers and DJ pool tags
3. **Validation** - Checks against MusicBrainz and Spotify to get the official name
4. **Logging** - Stores the play in the database with timestamp
5. **Counting** - Updates play counts for the current chart week

Everything happens automatically, in real-time, so you're always seeing the latest data.

## Stay Connected

Check back often to see how your favorite tracks are climbing the chart! The Top 10 updates throughout the week, so today's #5 might be tomorrow's #1.

**Remember:** This isn't a popularity contest from streaming services - this is what's actually playing on Muddy's Music Cafe, chosen by the DJs and requested by listeners like you!

---

*Have questions about the chart or how it works? Contact Muddy's Music Cafe through their website or social media.*
