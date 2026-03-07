'use client'
import React from 'react'
import { motion } from 'framer-motion'

interface BentoGridProps {
  children: React.ReactNode
}

export function BentoGrid({ children }: BentoGridProps) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
      gridAutoRows: 'minmax(200px, auto)',
      gap: '1rem',
      padding: '1rem 0'
    }}>
      {children}
    </div>
  )
}

interface BentoItemProps {
  children: React.ReactNode
  colSpan?: 1 | 2 | 3
  rowSpan?: 1 | 2
  className?: string
}

export function BentoItem({ children, colSpan = 1, rowSpan = 1, className = '' }: BentoItemProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      className={`card ${className}`}
      style={{
        gridColumn: `span ${colSpan}`,
        gridRow: `span ${rowSpan}`,
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {children}
    </motion.div>
  )
}
