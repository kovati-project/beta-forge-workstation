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
  services: {},              // { [name]: { status, port, gpus, uptime, cpu, mem } }
  alertCount: 0,             // int — drives Monitor badge
  systemMode: 'workstation', // 'workstation' | 'appliance'
};

// Reducer
function appReducer(state, action) {
  switch (action.type) {
    case 'SET_GPU_STATUS': {
      const { activeProfile, switching, gpus, runningServices } = action.payload;
      return {
        ...state,
        activeProfile: activeProfile || state.activeProfile,
        switching: switching !== undefined ? switching : state.switching,
        gpus: gpus || state.gpus,
        runningServices: runningServices || state.runningServices,
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

  const value = {
    state,
    dispatch,
    setGpuStatus,
    setServices,
    setAlertCount,
    setSystemMode,
    setLastSwitched,
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
