import React from 'react';

interface GameInfoProps {
    credits: number;
    betAmount: number;
    currentWin: number;
}

const InfoBox: React.FC<React.PropsWithChildren<{ label: string }>> = ({ label, children }) => (
    <div className="bg-brand-panel-bg rounded-lg px-3 py-1 text-center">
        <div className="text-xs text-slate-400">{label}</div>
        <div className="text-base font-semibold text-white">{children}</div>
    </div>
);

const GameInfo: React.FC<GameInfoProps> = ({ credits, betAmount, currentWin }) => {
    return (
        <div className="flex items-center gap-2">
            <InfoBox label="$MPS">
                {credits.toLocaleString()}
            </InfoBox>
            <InfoBox label="BET">
                {betAmount.toLocaleString()}
            </InfoBox>
            <InfoBox label="WIN">
                <span className={currentWin > 0 ? 'text-brand-green' : ''}>
                    {currentWin.toLocaleString()}
                </span>
            </InfoBox>
        </div>
    );
};

export default GameInfo;