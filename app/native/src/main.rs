//! Offline-only IQ decoder. No SDR/network/feed dependency is linked.
use std::io::{self, Read, Write};
use num_complex::Complex;
use xng_types::{AppInfo, Provenance, StationIdentity, Message};
enum Decoder {
    Acars(xng_mode_acars::AcarsChannelDecoder),
    Vdl2(xng_mode_vdl2::Vdl2ChannelDecoder),
    Hfdl(xng_mode_hfdl::HfdlChannelDecoder),
    Sonde(xng_mode_sonde::SondeChannelDecoder),
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let a:Vec<String>=std::env::args().collect();
    if a.len()!=6 {return Err("usage: radar-decode MODE RATE CENTER_HZ CHANNEL_HZ,... u8|f32".into());}
    let rate:f64=a[2].parse()?;let center:f64=a[3].parse()?;
    let mut decoders=Vec::new();
    for channel in a[4].split(',') {
        let freq:u64=channel.parse()?;let offset=freq as f64-center;
        let d=match a[1].as_str() {
            "acars"=>Decoder::Acars(xng_mode_acars::AcarsChannelDecoder::new(rate,offset)?),
            "vdl2"=>Decoder::Vdl2(xng_mode_vdl2::Vdl2ChannelDecoder::new(rate,offset)?),
            "hfdl"=>Decoder::Hfdl(xng_mode_hfdl::HfdlChannelDecoder::new(rate,offset)?),
            "sonde"=>Decoder::Sonde(xng_mode_sonde::SondeChannelDecoder::new(rate,offset)?),
            _=>return Err("unknown mode".into()),
        };decoders.push((freq,d));
    }
    let source=Provenance{station:StationIdentity::new("LOCAL"),app:AppInfo::xng(),sdr:None,channel:None};
    let stride=match a[5].as_str(){"u8"=>2,"i16"=>4,"f32"=>8,_=>return Err("unknown IQ format".into())};
    let mut input=io::stdin().lock();let mut output=io::BufWriter::new(io::stdout().lock());
    let mut buf=vec![0u8;65536];let mut pending=Vec::new();
    loop {
        let n=input.read(&mut buf)?;if n==0 {break;}
        pending.extend_from_slice(&buf[..n]);let used=pending.len()/stride*stride;
        let iq:Vec<Complex<f32>>=pending[..used].chunks_exact(stride).map(|b| {
            if stride==2 {Complex::new((b[0] as f32-127.5)/128.,(b[1] as f32-127.5)/128.)}
            else if stride==4 {Complex::new(i16::from_le_bytes(b[0..2].try_into().unwrap()) as f32/32768.,i16::from_le_bytes(b[2..4].try_into().unwrap()) as f32/32768.)}
            else {Complex::new(f32::from_le_bytes(b[0..4].try_into().unwrap()),f32::from_le_bytes(b[4..8].try_into().unwrap()))}
        }).collect();
        pending.drain(..used);
        for (freq,decoder) in &mut decoders {
            let messages:Vec<Message>=match decoder {
                Decoder::Acars(d)=>d.process(&iq).iter().map(|f|xng_mode_acars::to_message(f,*freq,d.level_dbfs(),d.noise_dbfs(),source.clone())).collect(),
                Decoder::Vdl2(d)=>d.process(&iq).iter().map(|f|xng_mode_vdl2::to_message(f,*freq,d.level_dbfs(),source.clone())).collect(),
                Decoder::Hfdl(d)=>d.process(&iq).iter().map(|f|xng_mode_hfdl::to_message(f,*freq,d.level_dbfs(),source.clone())).collect(),
                Decoder::Sonde(d)=>d.process(&iq).iter().map(|f|xng_mode_sonde::to_message(f,*freq,d.level_dbfs(),source.clone())).collect(),
            };
            for message in messages {if message.decode.crc_ok {serde_json::to_writer(&mut output,&message)?;output.write_all(b"\n")?;}}
        }output.flush()?;
    }
    if !pending.is_empty(){return Err("truncated IQ sample".into());}Ok(())
}
