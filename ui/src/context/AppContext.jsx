import React, { createContext, useReducer, useCallback } from 'react';

// Create context
export const AppContext = createContext();

// Initial state
const initialState = {
  activeProfile: null,       // string | null
  switching: false,          // bool — drives 1s polling mode
  lastSwitched: null,        // epoch float
  runningServices: [],       // string[]
  gpus: [],                  // GPU status array from /status
  gpuTelemetry: null,        // { available, error } from /status; null until first poll
  switchTarget: null,        // { name, since, confirmed } for a switch this UI started
  services: {},              // { [name]: { status, port, gpus, uptime, cpu, mem } }
  alertCount: 0,             // int — drives Monitor badge
  systemMode: 'workstation', // 'workstation' | 'appliance'
};

// How long an activation this UI just started counts as "switching" before
// /status has confirmed it. Covers a poll that was already in flight when the
// POST went out and still reports switching: false.
export const SWITCH_CONFIRM_GRACE_MS = 10000;

// Reducer
export function appReducer(state, action) {
  switch (action.type) {
    case 'SET_GPU_STATUS': {
      // /status sends snake_case; map it to the camelCase state shape here.
      // A field that is absent (undefined) keeps the previous value, but an
      // explicit null from the backend (e.g. no active profile) is authoritative.
      const p = action.payload || {};
      const now = action.now ?? Date.now();
      const pick = (snake, camel) => (p[snake] !== undefined ? p[snake] : p[camel]);
      const activeProfile = pick('active_profile', 'activeProfile');
      const lastSwitched = pick('last_switched', 'lastSwitched');
      const runningServices = pick('running_services', 'runningServices');
      const gpuTelemetry = pick('gpu_telemetry', 'gpuTelemetry');
      const serverSwitching = p.switching !== undefined ? Boolean(p.switching) : state.switching;

      // Track a switch this UI started: once /status reports it, it is
      // confirmed; once a confirmed switch ends, the target is cleared. Until
      // confirmed (and within the grace period) keep showing it as switching.
      let switchTarget = state.switchTarget;
      if (switchTarget) {
        if (serverSwitching) {
          switchTarget = switchTarget.confirmed ? switchTarget : { ...switchTarget, confirmed: true };
        } else if (switchTarget.confirmed || now - switchTarget.since > SWITCH_CONFIRM_GRACE_MS) {
          switchTarget = null;
        }
      }
      const switching = serverSwitching || Boolean(switchTarget && !switchTarget.confirmed);

      return {
        ...state,
        activeProfile: activeProfile !== undefined ? activeProfile : state.activeProfile,
        switching,
        switchTarget,
        lastSwitched: lastSwitched !== undefined ? lastSwitched : state.lastSwitched,
        gpus: Array.isArray(p.gpus) ? p.gpus : state.gpus,
        gpuTelemetry: gpuTelemetry !== undefined ? gpuTelemetry : state.gpuTelemetry,
        runningServices: Array.isArray(runningServices) ? runningServices : state.runningServices,
      };
    }
    case 'SWITCH_STARTED': {
      // POST /activate was accepted; the backend has already raised its
      // switching flag, so show it now instead of on the next poll.
      return {
        ...state,
        switching: true,
        switchTarget: {
          name: action.payload,
          since: action.now ?? Date.now(),
          confirmed: false,
        },
      };
    }
    case 'SET_SERVICES': {
      const { services } = action.payload;
      return {
        ...state,
        services: services || state.services,
      };
    }
    case 'SET_ALERT_COUNT': {
      return {
        ...state,
        alertCount: action.payload,
      };
    }
    case 'SET_SYSTEM_MODE': {
      return {
        ...state,
        systemMode: action.payload,
      };
    }
    case 'SET_LAST_SWITCHED': {
      return {
        ...state,
        lastSwitched: action.payload,
      };
    }
    default:
      return state;
  }
}

// Provider component
export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  const setGpuStatus = useCallback((data) => {
    dispatch({ type: 'SET_GPU_STATUS', payload: data });
  }, []);

  const setServices = useCallback((data) => {
    dispatch({ type: 'SET_SERVICES', payload: data });
  }, []);

  const setAlertCount = useCallback((count) => {
    dispatch({ type: 'SET_ALERT_COUNT', payload: count });
  }, []);

  const setSystemMode = useCallback((mode) => {
    dispatch({ type: 'SET_SYSTEM_MODE', payload: mode });
  }, []);

  const setLastSwitched = useCallback((timestamp) => {
    dispatch({ type: 'SET_LAST_SWITCHED', payload: timestamp });
  }, []);

  const startSwitch = useCallback((profileName) => {
    dispatch({ type: 'SWITCH_STARTED', payload: profileName });
  }, []);

  const value = {
    state,
    dispatch,
    setGpuStatus,
    setServices,
    setAlertCount,
    setSystemMode,
    setLastSwitched,
    startSwitch,
  };

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
}

// Custom hook for consuming context
export function useApp() {
  const context = React.useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
}
