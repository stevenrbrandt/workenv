#!/usr/bin/perl
use strict;
use FileHandle;
die unless(-r $ARGV[0]);

my $first_line = 0;
my $fd = new FileHandle;
my $fw = new FileHandle;
my $rw = new FileHandle;
my $last_was_blank = 0;
mkdir("chapters");
my $chap=0;
open($fd,$ARGV[0]) or die;
while(<$fd>) {
  last if(/^\s*<end>/);
  next if(/^\s*#/);
  if(/^\s*<(?:no|)chapter(?:=(["'])(.*)\1)?(\s+sect)?>/) {
    my $chname = $2;
    $chname =~ s/.*?://;
    $first_line = 1;
    print $rw "}\n\n";
    #print $fw "</textarea></body></html>\n";
    $chap++;
    my $fname = sprintf("chapters/chap%03d.txt",$chap);
    my $rname = sprintf("chapters/chap%03d.rtf",$chap);
    close($fw);
    close($rw);
    open($fw,">$fname") or die;
    print $fw $chname,"\n";
    #print $fw "<html><body><form><textarea cols='90' rows='150'>";
    open($rw,">$rname") or die;
    print $rw "{\\rtf1\\ansi\\deff0 {\\fonttbl \n";
    print $rw "{\\f0 Courier New;}}\\fs24\n";
    printf $rw "\\margl%d\\margr%d\\margt%d\\margb%d ",1800,1800,1400,1400;
    printf $rw "\\paperw%d\\paperh%d",8.5*1440.0,11*1440.0;
    print $rw "{\\pard \\par}";
    #print $rw sprintf("{\\pard >>> Chapter %d <<<\\par}\n",$chap);
  } else {
    if($first_line) {
      next if(/^\s*$/);
      $first_line=0;
    }
    #s/^\s*#.*//;
    next if(/^\s*#/);
    my $raw = accent($_);
    #s/^/>/;
    #s/<i>\s*/_/g;
    #s/\s*<\/i>/_/g;
    my $blank = /^\s*$/;
    #print $fw $_ unless($blank and $last_was_blank);
    $_ = $raw;
    s/<scene.*>/{\\pard\\qc # \\par}\n{\\pard \\par}/;
    s/<i>/\\i /g;
    s/<\/i>/\\i0 /g;
    s/<authornote=(['"])(.*)\1>/{\\pard A\/N: \\i $2 \\i0\\par}/;
    s/<[^>]*>//g;
    s/.*/{\\pard $& \\par}/;
    #s/\\'e/\\u233\\'e9/g;
    print $rw $_ unless($blank and $last_was_blank);
    $last_was_blank=$blank;
  }
}
print $rw "}\n\n";
#print $fw "</textarea></body></html>\n";
close($rw);
close($fw);
sub accent {
  my $txt = shift;
  $txt =~ s/\\+'e/\\u233\\'e9/g;
  $txt =~ s/<'e>/\\u233\\'e9/g;
  $txt =~ s/<'a>/\\u225\\'e1/g;
  $txt =~ s/<'o>/\\u243\\'f3/g;
  $txt =~ s/<'i>/\\u237\\'ed/g;
  $txt =~ s/<'u>/\\u250\\'fa/g;
  return $txt
}
