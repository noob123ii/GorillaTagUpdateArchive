import React from 'react';

export default function Layout({ children }) {
  return (
    <>
      <style>
        {`
          @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
          
          * {
            font-family: 'Space Grotesk', sans-serif;
          }
        `}
      </style>
      {children}
    </>
  );
}