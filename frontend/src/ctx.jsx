import { createContext, useContext } from 'react'
export const AppCtx = createContext({ refreshKey: 0, bump: () => {}, openRefine: () => {} })
export const useApp = () => useContext(AppCtx)
