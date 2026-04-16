import React from 'react';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: React.ReactNode;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children }) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-70 flex justify-center items-center z-50">
            <div className="bg-brand-panel-bg border border-brand-panel-light rounded-2xl shadow-lg p-6 max-w-sm w-full mx-4">
                <div className="text-center mb-4">
                    <h2 className="text-2xl font-semibold text-white">{title}</h2>
                </div>
                <div className="text-slate-200">{children}</div>
            </div>
        </div>
    );
};

export default Modal;