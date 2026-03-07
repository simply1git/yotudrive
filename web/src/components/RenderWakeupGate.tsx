'use client'
import { useState, useEffect } from 'react'
import { authApi } from '@/lib/api'
import { motion, AnimatePresence } from 'framer-motion'
import { Rocket, Satellite, Zap } from 'lucide-react'

export function RenderWakeupGate({ children }: { children: React.ReactNode }) {
    const [isWaking, setIsWaking] = useState(true)
    const [errorCount, setErrorCount] = useState(0)

    useEffect(() => {
        let isMounted = true
        
        const checkHealth = async () => {
            try {
                // Perform a simple health check. 
                // Render will automatically start waking up as soon as this request hits.
                await authApi.health()
                if (isMounted) setIsWaking(false)
            } catch (err) {
                if (isMounted) {
                    setErrorCount(prev => prev + 1)
                    // Retry every 3 seconds while waking
                    setTimeout(checkHealth, 3000)
                }
            }
        }

        checkHealth()
        
        return () => { isMounted = false }
    }, [])

    return (
        <>
            <AnimatePresence>
                {isWaking && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[9999] bg-slate-950 flex flex-col items-center justify-center p-6 text-center"
                    >
                        <div className="mesh-bg opacity-30" />
                        
                        <motion.div
                            animate={{ 
                                scale: [1, 1.1, 1],
                                rotate: [0, 5, -5, 0]
                            }}
                            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                            className="relative mb-12"
                        >
                            <div className="absolute inset-0 bg-accent blur-[60px] opacity-20 animate-pulse" />
                            <Rocket size={80} className="text-accent relative z-10" />
                        </motion.div>

                        <h2 className="text-3xl font-display font-black text-white tracking-tighter mb-4 uppercase italic">
                            Waking up the <span className="text-glow text-accent">Cosmos</span>
                        </h2>
                        
                        <div className="max-w-md">
                            <p className="text-muted text-sm leading-relaxed mb-8 uppercase tracking-widest font-bold">
                                Initializing secure bridge to the YotuDrive Engine...
                            </p>
                        </div>

                        <div className="flex gap-4 mb-12">
                            {[0, 1, 2].map((i) => (
                                <motion.div
                                    key={i}
                                    animate={{ 
                                        opacity: [0.2, 1, 0.2],
                                        y: [0, -4, 0]
                                    }}
                                    transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
                                    className="w-2 h-8 bg-accent rounded-full shadow-glow"
                                />
                            ))}
                        </div>

                        <div className="flex flex-col items-center gap-3">
                            <span className="flex items-center gap-2 text-[10px] font-mono text-accent/60 tracking-[0.2em] uppercase font-bold">
                                <Satellite size={12} className="animate-spin-slow" /> uplink_status: searching
                            </span>
                            {errorCount > 2 && (
                                <span className="flex items-center gap-2 text-[10px] font-mono text-warning/60 tracking-[0.2em] uppercase font-bold text-glow-warning">
                                    <Zap size={12} /> protocol: warming_up
                                </span>
                            )}
                        </div>

                        <div className="absolute bottom-10 left-10 text-[9px] font-mono text-white/10 uppercase tracking-widest leading-loose text-left">
                            render_service: sleeper_tier<br />
                            spin_up_time: ~30_60s<br />
                            connection: persistent
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
            {!isWaking && children}
        </>
    )
}
