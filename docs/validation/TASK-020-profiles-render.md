# TASK-020 — Validate all profiles render in the UI

**Issue:** #10
**Result: FAIL** — **zero** of 11 profiles render. The Loadout page's profile grid is
permanently empty.

## Count correction confirmed

`profiles.yaml` defines **11** profiles, not the 9 originally assumed. `GET /loadouts`
returns all 11:

```
inference-small        inference-pair-a      inference-pair-b
inference-4gpu         dual-stack            image-studio
training-lora-image    training-lora-text    training-unsloth
inference-4gpu-large   idle
```

The backend is correct and complete. The failure is entirely frontend.

## Root cause — response shape mismatch

`GET /loadouts` returns the profiles as **top-level keys of the response object**.
There is no `profiles` wrapper:

```
top-level keys: ['inference-small', 'inference-pair-a', ..., 'idle']
has "profiles" key: False
```

But `useLoadouts` reads exactly that key (`ui/src/hooks/useLoadouts.js:15`):

```js
setProfiles(data.profiles || []);
```

`data.profiles` is `undefined`, so `profiles` is set to `[]` on every poll — all 11
profiles are discarded immediately after a successful fetch.

## Consequence

The chain is unbroken from hook to render:

- `ui/src/pages/Loadout.jsx:8` — `const { profiles, error } = useLoadouts();`
- `ui/src/pages/Loadout.jsx:14` — `<ProfileGrid profiles={profiles} loading={!profiles} error={error} />`

`profiles` is `[]`, so `ProfileGrid` receives an empty array and renders no cards.
Worse, `loading={!profiles}` evaluates `![]` → `false`, so the grid does not even show
a loading state — the user sees a silently empty panel with no error and no spinner.
The fetch succeeded, so `error` is `null` too.

This also means **no profile can be activated from the UI at all**, since there is
nothing to click. It is very likely the practical reason the profile-activation
tasks (#11-#14, #17-#19) have never been exercised through the interface.

## Fix

One line. Either unwrap on the client:

```js
setProfiles(data.profiles || data || []);
```

or, better, normalise the object into the array shape `ProfileGrid` expects, keyed by
profile name — the API returns a dict, not a list, so a bare fallback still hands
`ProfileGrid` an object where it expects an array.

## Verdict

Fails. High severity: this is the primary control surface of the application and it
is empty. Fix is small and well understood.
