# What to build next

Suggested follow-up features to make PaceTrail more production-ready and engaging:

1. **Segments** – Define named segments (e.g. “Hill climb”, “Sprint finish”). Record segment times per activity and show segment leaderboards (per user or global).

2. **Challenges** – Time-bound goals (e.g. “Run 50 km this month”, “10 rides in 30 days”). Track progress and show completion badges.

3. **Leaderboards** – Public or friends-only leaderboards by segment, challenge, or weekly/monthly distance by sport.

4. **Notifications** – In-app or email: new follower, like/comment on your activity, challenge reminder. Use Redis or a queue for delivery; optional push (e.g. web push).

5. **Real-time feed** – WebSocket or SSE for live activity updates in the feed when followed users post.

6. **Avatar upload** – Store profile images (S3 or local); resize and serve with a CDN or signed URLs.

7. **Activity edit** – Edit title/visibility after create; optional “replace file” to re-parse GPX/TCX and recompute stats.

8. **Rate limiting** – Implement the rate-limit stub with Redis (e.g. sliding window) and return 429 with Retry-After.

9. **Background jobs** – Move GPX/TCX parsing into a worker (Celery/RQ) so uploads return quickly and stats are computed asynchronously; optional retries and dead-letter queue.

10. **Search and filters** – Search activities by title/description; filter feed by date range and sport (partially done); filter profile activities the same way.

11. **Privacy** – Block list, hide stats (e.g. “Private” activity hides distance/pace from others), and optional “approve followers”.

12. **Mobile** – PWA with offline support, or React Native / Expo app reusing the same API.
