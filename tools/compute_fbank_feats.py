

import argparse
import logging

import torchaudio
import torchaudio.compliance.kaldi as kaldi

import wenet.dataset.kaldi_io as kaldi_io


def parse_opts():
    parser = argparse.ArgumentParser(description='training your network')
    parser.add_argument('--num_mel_bins',
                        default=80,
                        type=int,
                        help='Number of triangular mel-frequency bins')
    parser.add_argument('--frame_length',
                        type=int,
                        default=25,
                        help='Frame length in milliseconds')
    parser.add_argument('--frame_shift',
                        type=int,
                        default=10,
                        help='Frame shift in milliseconds')
    parser.add_argument('--dither',
                        type=int,
                        default=0.0,
                        help='Dithering constant (0.0 means no dither)')
    parser.add_argument('--segments', default=None, help='segments file')
    parser.add_argument('wav_scp', help='wav scp file')
    parser.add_argument('out_ark', help='output ark file')
    parser.add_argument('out_scp', help='output scp file')
    args = parser.parse_args()
    return args


# wav format: <key> <wav_path>
def load_wav_scp(wav_scp_file):
    wav_list = []
    with open(wav_scp_file, 'r', encoding='utf8') as fin:
        for line in fin:
            arr = line.strip().split()
            assert len(arr) == 2
            wav_list.append((arr[0], arr[1]))
    return wav_list


# wav format: <key> <wav_path>
def load_wav_scp_dict(wav_scp_file):
    wav_dict = {}
    with open(wav_scp_file, 'r', encoding='utf8') as fin:
        for line in fin:
            arr = line.strip().split()
            assert len(arr) == 2
            wav_dict[arr[0]] = arr[1]
    return wav_dict


# Segments format: <key> <wav_key> <start> <end>
def load_wav_segments(wav_scp_file, segments_file):
    wav_dict = load_wav_scp_dict(wav_scp_file)
    audio_list = []
    with open(segments_file, 'r', encoding='utf8') as fin:
        for line in fin:
            arr = line.strip().split()
            assert len(arr) == 4
            key = arr[0]
            wav_file = wav_dict[arr[1]]
            start = float(arr[2])
            end = float(arr[3])
            audio_list.append((key, wav_file, start, end))
    return audio_list


if __name__ == '__main__':
    args = parse_opts()
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s')
    if args.segments is None:
        audio_list = load_wav_scp(args.wav_scp)
    else:
        audio_list = load_wav_segments(args.wav_scp, args.segments)

    count = 0
    with open(args.out_ark, 'wb') as ark_fout, \
         open(args.out_scp, 'w', encoding='utf8') as scp_fout:
        for item in audio_list:
            if len(item) == 2:
                key, wav_path = item
                waveform, sample_rate = torchaudio.load(wav_path)
            else:
                assert len(item) == 4
                key, wav_path, start, end = item
                sample_rate = torchaudio.info(wav_path).sample_rate
                frame_offset = int(start * sample_rate)
                num_frames = int((end - start) * sample_rate)
                waveform, sample_rate = torchaudio.load(
                    wav_path, frame_offset, num_frames)

            mat = kaldi.fbank(waveform,
                              num_mel_bins=args.num_mel_bins,
                              frame_length=args.frame_length,
                              frame_shift=args.frame_shift,
                              dither=args.dither,
                              energy_floor=0.0,
                              sample_frequency=sample_rate)
            mat = mat.detach().numpy()
            kaldi_io.write_ark_scp(key, mat, ark_fout, scp_fout)
            count += 1
            if count % 10000 == 0:
                logging.info('Progress {}/{}'.format(count, len(audio_list)))
