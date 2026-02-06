const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

const defaultFetchOptions: RequestInit = {
  credentials: "include",
};

async function refreshAccessToken(): Promise<string> {
  const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    ...defaultFetchOptions,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Refresh failed");
  }
  const data = await res.json();
  const token = data.access_token;
  if (token) setAccessToken(token);
  return token;
}

export async function api<T>(
  path: string,
  options: RequestInit & { params?: Record<string, string> } = {}
): Promise<T> {
  const { params, ...init } = options;
  let url = `${API_URL}${path}`;
  if (params && Object.keys(params).length) {
    url += "?" + new URLSearchParams(params).toString();
  }
  const token = getAccessToken();
  const headers: HeadersInit = {
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!headers["Content-Type"] && init.body && typeof init.body === "string")
    headers["Content-Type"] = "application/json";

  let res = await fetch(url, {
    ...defaultFetchOptions,
    ...init,
    headers,
  });

  if (res.status === 401) {
    try {
      await refreshAccessToken();
      const newToken = getAccessToken();
      if (newToken) {
        headers["Authorization"] = `Bearer ${newToken}`;
        res = await fetch(url, { ...defaultFetchOptions, ...init, headers });
      }
    } catch {
      setAccessToken(null);
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || Array.isArray(err.detail) ? err.detail.join(", ") : res.statusText);
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const message = err.detail || (Array.isArray(err.detail) ? err.detail.join(", ") : res.statusText);
    const e = new Error(message) as Error & { status?: number };
    e.status = res.status;
    throw e;
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const authApi = {
  signup: (data: { email: string; password: string; name: string; bio?: string }) =>
    api<{ id: string; email: string; name: string; bio: string | null }>(`/api/v1/auth/signup`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  login: (data: { email: string; password: string }) =>
    fetch(`${API_URL}/api/v1/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || "Login failed");
      }
      const data = await r.json();
      if (data.access_token) setAccessToken(data.access_token);
      return data as { access_token: string; expires_in: number };
    }),
  refresh: () =>
    fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    }).then(async (r) => {
      if (!r.ok) throw new Error("Refresh failed");
      const data = await r.json();
      if (data.access_token) setAccessToken(data.access_token);
      return data as { access_token: string; expires_in: number };
    }),
  logout: () =>
    fetch(`${API_URL}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).then(() => {
      setAccessToken(null);
    }),
};

export type User = { id: string; email: string; name: string; bio: string | null; avatar_url?: string | null };
export type UserPublic = { id: string; name: string; bio: string | null; avatar_url?: string | null };
export type ActivityStatus = "draft" | "processing" | "ready" | "failed";

export type ActivityItem = {
  id: string;
  user_id: string;
  title: string;
  sport_type: "run" | "ride" | "walk";
  visibility: string;
  started_at: string;
  distance_m: number | null;
  duration_s: number | null;
  elevation_gain_m: number | null;
  calories: number | null;
  polyline: string | null;
  created_at: string;
  like_count: number;
  comment_count: number;
  liked_by_me: boolean;
  user: UserPublic | null;
  status?: ActivityStatus;
};
export type ActivityDetail = ActivityItem & {
  splits: { index: number; distance_m: number; duration_s: number; pace_per_km_s?: number; speed_kmh?: number }[] | null;
  elevation_profile: { distance_m: number; elevation_m: number }[] | null;
  status?: ActivityStatus;
  error_message?: string | null;
  rank_eligible?: boolean;
  rank_excluded_reason?: string | null;
  max_speed_kmh?: number | null;
  segments?: SegmentEffortResponse[] | null;
};
export type ActivityStatusResponse = { status: ActivityStatus; error_message?: string | null };
export type CommentItem = { id: string; user_id: string; activity_id: string; body: string; created_at: string; user: UserPublic | null };

export const usersApi = {
  me: () => api<User>("/api/v1/users/me"),
  updateMe: (data: { name?: string; bio?: string }) => api<User>("/api/v1/users/me", { method: "PATCH", body: JSON.stringify(data) }),
  search: (q: string, limit = 20, offset = 0) =>
    api<UserPublic[]>("/api/v1/users/search", { params: { q, limit: String(limit), offset: String(offset) } }),
  get: (id: string) => api<UserPublic>(`/api/v1/users/${id}`),
};

export const activitiesApi = {
  feed: (params?: { sport_type?: string; date_from?: string; date_to?: string; limit?: number; offset?: number }) =>
    api<ActivityItem[]>("/api/v1/activities/feed", { params: params as Record<string, string> }),
  get: (id: string) => api<ActivityDetail>(`/api/v1/activities/${id}`),
  getStatus: (id: string) => api<ActivityStatusResponse>(`/api/v1/activities/${id}/status`),
  getStream: (id: string, max_points = 500) =>
    api<{ lat: number; lon: number; elevation_m?: number | null; cumulative_distance_m?: number | null }[]>(
      `/api/v1/activities/${id}/stream`,
      { params: { max_points: String(max_points) } }
    ),
  listByUser: (userId: string, limit = 20, offset = 0) =>
    api<ActivityItem[]>(`/api/v1/activities/user/${userId}`, { params: { limit: String(limit), offset: String(offset) } }),
  create: (form: FormData) =>
    fetch(`${API_URL}/api/v1/activities`, {
      method: "POST",
      credentials: "include",
      headers: getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {},
      body: form,
    }).then(async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || r.statusText);
      }
      return r.json();
    }),
  delete: (id: string) => api(`/api/v1/activities/${id}`, { method: "DELETE" }),
};

export const followsApi = {
  follow: (userId: string) => api(`/api/v1/follows/${userId}`, { method: "POST" }),
  unfollow: (userId: string) => api(`/api/v1/follows/${userId}`, { method: "DELETE" }),
  isFollowing: (userId: string) => api<boolean>(`/api/v1/follows/${userId}/following`),
  following: (limit = 50, offset = 0) => api<UserPublic[]>("/api/v1/follows/me/following", { params: { limit: String(limit), offset: String(offset) } }),
  followers: (limit = 50, offset = 0) => api<UserPublic[]>("/api/v1/follows/me/followers", { params: { limit: String(limit), offset: String(offset) } }),
};

export const likesApi = {
  like: (activityId: string) => api(`/api/v1/likes/activities/${activityId}`, { method: "POST" }),
  unlike: (activityId: string) => api(`/api/v1/likes/activities/${activityId}`, { method: "DELETE" }),
};

export const commentsApi = {
  list: (activityId: string) => api<CommentItem[]>(`/api/v1/comments/activities/${activityId}`),
  create: (activityId: string, body: string) =>
    api<CommentItem>(`/api/v1/comments/activities/${activityId}`, { method: "POST", body: JSON.stringify({ body }) }),
};

export type NotificationItem = {
  id: string;
  recipient_user_id: string;
  actor_user_id: string;
  type: "follow" | "like" | "comment" | "rank_up" | "segment_pr" | "segment_kom";
  activity_id: string | null;
  comment_id: string | null;
  is_read: boolean;
  data?: {
    old_tier?: string;
    new_tier?: string;
    new_tier_name?: string;
    score?: number;
    segment_id?: string;
    segment_name?: string;
    effort_time_s?: number;
    type?: "pr" | "kom";
  } | null;
  created_at: string;
  actor_name: string | null;
};

export type SegmentCreate = {
  name: string;
  description?: string;
  polyline: string;
  is_public: boolean;
};

export type SegmentResponse = {
  id: string;
  owner_user_id: string;
  name: string;
  description?: string | null;
  polyline: string;
  distance_m: number;
  is_public: boolean;
  created_at: string;
};

export type SegmentEffortResponse = {
  id: string;
  segment_id: string;
  activity_id: string;
  user_id: string;
  segment_name?: string | null;
  effort_time_s: number;
  effort_distance_m: number;
  avg_speed_kmh: number;
  started_at: string;
  visibility: string;
  is_pr?: boolean | null;
};

export type SegmentLeaderboardItem = {
  user_id: string;
  name: string | null;
  activity_id: string;
  effort_time_s: number;
  effort_distance_m: number;
  avg_speed_kmh: number;
  started_at: string;
  is_kom?: boolean | null;
};

export type SegmentLeaderboardResponse = {
  segment: SegmentResponse;
  items: SegmentLeaderboardItem[];
  kom?: {
    user_id: string;
    name: string | null;
    activity_id: string;
    effort_time_s: number;
    started_at: string;
  } | null;
};

export const notificationsApi = {
  list: (params?: { limit?: number; cursor?: string }) =>
    api<NotificationItem[]>("/api/v1/notifications", {
      params: params as Record<string, string> | undefined,
    }),
  unreadCount: () => api<{ count: number }>("/api/v1/notifications/unread-count"),
  markRead: (body: { ids?: string[]; mark_all?: boolean }) =>
    api<{ marked: number }>("/api/v1/notifications/mark-read", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export const segmentsApi = {
  create: (payload: SegmentCreate) =>
    api<SegmentResponse>("/api/v1/segments", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  list: (params?: { query?: string; limit?: number; offset?: number }) =>
    api<SegmentResponse[]>("/api/v1/segments", {
      params: params
        ? {
            query: params.query ?? "",
            limit: String(params.limit ?? 20),
            offset: String(params.offset ?? 0),
          }
        : undefined,
    }),
  get: (id: string) => api<SegmentResponse>(`/api/v1/segments/${id}`),
  leaderboard: (id: string) => api<SegmentLeaderboardResponse>(`/api/v1/segments/${id}/leaderboard`),
  myEfforts: (id: string) => api<SegmentEffortResponse[]>(`/api/v1/segments/${id}/my-efforts`),
};

export type AthleteSummaryTotals = {
  activities: number;
  distance_m: number;
  moving_time_s: number;
  elevation_gain_m: number;
  calories: number;
};
export type AthleteSummaryBySport = {
  sport_type: string;
  activities: number;
  distance_m: number;
  moving_time_s: number;
  elevation_gain_m: number;
};
export type AthleteSummary = {
  range: string;
  from: string;
  to: string;
  totals: AthleteSummaryTotals;
  by_sport: AthleteSummaryBySport[];
};
export type AthleteWeek = { week_start: string; distance_m: number; activities: number };

export const athletesApi = {
  getSummary: (userId: string | undefined, range: "7d" | "30d" | "ytd") =>
    userId
      ? api<AthleteSummary>(`/api/v1/athletes/${userId}/summary`, { params: { range } })
      : api<AthleteSummary>("/api/v1/athletes/me/summary", { params: { range } }),
  getWeeks: (userId: string | undefined, weeks = 12) =>
    userId
      ? api<AthleteWeek[]>(`/api/v1/athletes/${userId}/weeks`, { params: { weeks: String(weeks) } })
      : api<AthleteWeek[]>("/api/v1/athletes/me/weeks", { params: { weeks: String(weeks) } }),
};

export type RankTierId = "bronze" | "silver" | "gold" | "platinum" | "diamond" | "world_class";

export type RankBreakdown = {
  runs_count: number;
  active_days: number;
  total_distance_m: number;
  total_time_s: number;
  avg_speed_kmh: number;
  total_elevation_gain_m: number;
  total_calories: number;
  score: number;
};

export type RankMeResponse = {
  user_id: string;
  rank_tier: RankTierId | null;
  rank_tier_name: string | null;
  rank_score: number | null;
  rank_range_days: number;
  rank_last_computed_at: string | null;
  rank_progress: number | null;
  rank_next_tier: RankTierId | null;
  breakdown: RankBreakdown | null;
};

export type TierInfo = {
  id: RankTierId;
  name: string;
  min_score: number;
  max_score: number | null;
};

export type RunLeaderboardItem = {
  user_id: string;
  name: string;
  rank_tier: RankTierId | null;
  rank_tier_name: string | null;
  rank_score: number | null;
  runs_count_public: number;
  total_distance_public_m: number;
};

export type RunLeaderboardResponse = {
  range_days: number;
  items: RunLeaderboardItem[];
};

export type RankSnapshotItem = {
  date: string; // YYYY-MM-DD
  tier_id: string;
  tier_name: string;
  score: number;
};

export type RankHistoryResponse = {
  user_id: string;
  scope: "private" | "public";
  days: number;
  items: RankSnapshotItem[];
};

export const ranksApi = {
  getMe: () => api<RankMeResponse>("/api/v1/ranks/me"),
  recomputeMe: () => api<{ status: string; job_id?: string; result?: RankMeResponse }>("/api/v1/ranks/me/recompute", { method: "POST" }),
  getRecomputeStatus: (jobId: string) =>
    api<{ status: string; result?: RankMeResponse; error?: string }>(`/api/v1/ranks/me/recompute/${jobId}`),
  getTiers: () => api<TierInfo[]>("/api/v1/ranks/tiers"),
  getUser: (userId: string) => api<RankMeResponse>(`/api/v1/ranks/users/${userId}`),
  getHistoryMe: (days = 30) =>
    api<RankHistoryResponse>("/api/v1/ranks/me/history", { params: { days: String(days) } }),
  getHistoryUser: (userId: string, days = 30) =>
    api<RankHistoryResponse>(`/api/v1/ranks/users/${userId}/history`, { params: { days: String(days) } }),
  getRunLeaderboard: (limit = 50) =>
    api<RunLeaderboardResponse>("/api/v1/ranks/leaderboards/runs", {
      params: { range: "30d", limit: String(limit) },
    }),
  getRunLeaderboardFollowing: (limit = 50) =>
    api<RunLeaderboardResponse>("/api/v1/ranks/leaderboards/runs/following", {
      params: { range: "30d", limit: String(limit) },
    }),
};
