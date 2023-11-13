#!/usr/bin/perl
use strict;
use FileHandle;
my $fd = new FileHandle;
my $sum = 0;
my $off = 0;
if($#ARGV >= 0) {
    $off=1*$ARGV[0];
}
my $sub = 0;
if($#ARGV >= 1) {
    $sub=1*$ARGV[1];
}
open($fd,"toc.txt");
while(<$fd>) {
  chomp;
  if(/(\d+)$/) {
    $sum += 1*$1;
  }
}
close($fd);

my $sum2=0;
open($fd,"toc.txt");
while(my $line=<$fd>) {
  next if($line =~ /(problem|note):/);
  chomp($line);
  if($line=~/(\d+)$/) {
    $sum2 += 1*$1;
  }
  if($line =~ /^Ch: +(\d+),/) {
     my $n = $off + $1;
     $line = sprintf("Ch:%3d,%s",$n,$');
  }
  printf("%s %6.0f %10.0f\n",$line,100.0*$sum2/$sum,$sum2);
}
close($fd);
if($sub > 0) {
    my $diff = $sum - $sub;
    print "\nSUM = $sum = SUM - $sub = $diff\n";
} else {
    print "\nSUM = $sum\n";
}
