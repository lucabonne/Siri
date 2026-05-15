"""Speech subsystem — speech-to-text and text-to-speech backends.

Backend modules register themselves when imported. Discovery imports only the
specific backend it is considering so importing ``openjarvis.speech`` stays
lightweight.
"""
