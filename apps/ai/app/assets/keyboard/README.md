# Clavier mécanique enregistré (team 12, Amine K.)

28 extraits de 0,45 s (`k00.mp3` … `k27.mp3`) tirés de deux passages de frappe continue (9,6 → 15,9 s et
28,4 → 35,1 s) d'un enregistrement de clavier mécanique choisi à l'oreille par l'équipe (« mechanical keyboard
sound.mp3 »). Mis au format de la voix (mono, 44,1 kHz, 128 kb/s, sans en-tête Xing/ID3) et normalisés à −30 LUFS
pour rester derrière la voix :

```
ffmpeg -ss 9.6 -t 6.3 -i src.mp3 -ac 1 -ar 44100 a.wav ; ffmpeg -ss 28.4 -t 6.7 -i src.mp3 -ac 1 -ar 44100 b.wav
ffmpeg -i a.wav -i b.wav -filter_complex "[0][1]concat=n=2:v=0:a=1,loudnorm=I=-30:TP=-4:LRA=11" all.wav
# puis, toutes les 0,45 s : ffmpeg -ss T -t 0.45 -i all.wav -ac 1 -ar 44100 -c:a libmp3lame -b:a 128k -write_xing 0 -id3v2_version 0 kNN.mp3
```

Lus dans l'ordre par `services/fillers.keep_typing` (départ aléatoire à chaque attente). Sans ces fichiers, le
clavier synthétisé de `fillers.synthesized_typing` prend le relais.
