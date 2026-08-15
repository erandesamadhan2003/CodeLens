import React, { type ButtonHTMLAttributes } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'light';
  size?: 'sm' | 'lg';
}

export default function Button({ 
  children, 
  variant = 'primary', 
  size = 'lg', 
  className = '', 
  ...props 
}: ButtonProps) {
  
  const baseClasses = "inline-flex items-center justify-center border-2 border-ink rounded-[6px] font-display font-bold uppercase transition-all active:translate-x-[2px] active:translate-y-[2px]";
  
  const sizeClasses = {
    sm: "px-5 py-2 text-base",
    lg: "px-8 py-4 text-lg",
  };
  
  const variantClasses = {
    primary: "bg-accent text-ink shadow-[4px_4px_0px_#0A0A0A] active:shadow-[2px_2px_0px_#0A0A0A]",
    light: "bg-paper text-ink shadow-[4px_4px_0px_#FF5A1F] active:shadow-[2px_2px_0px_#FF5A1F]",
  };

  return (
    <button 
      className={`${baseClasses} ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
